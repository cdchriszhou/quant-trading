"""QMT / MiniQMT Broker Adapter — 迅投量化交易平台对接.

QMT (Quantitative Trading Mini-Platform) is the most popular retail quant
trading platform in China. It provides a Python API (xtquant) for:
  - Order submission & cancellation
  - Position & account queries
  - Real-time market data (Level-1)

Setup (user must do this once):
  1. Install QMT client from your broker (国金/华泰/中泰/etc.)
  2. Install xtquant Python package:
       pip install xtquant
     Or copy the xtquant folder from QMT installation directory.
  3. Login to QMT client → Settings → enable "本地Python接口"
  4. Set QMT_USER_DIR in .env to the QMT user data directory:
       QMT_USER_DIR=/path/to/QMT/userdata_mini
       QMT_ACCOUNT_ID=your_account_id

Usage in .env:
    BROKER_TYPE=qmt
    QMT_USER_DIR=/Users/xxx/qmt/userdata_mini
    QMT_ACCOUNT_ID=8888888888
"""

import asyncio
import datetime
import logging
import os
from pathlib import Path
from typing import Optional

from app.brokers.base import (
    BaseBroker, BrokerError, BrokerState, BrokerConnectionState,
    OrderSide, OrderType, OrderStatus,
    OrderRequest, OrderResult, PositionInfo, AccountInfo,
)

logger = logging.getLogger("broker.qmt")


class QMTBroker(BaseBroker):
    """Broker adapter for 迅投QMT / MiniQMT.

    Implements the BaseBroker interface using xtquant Python API.
    """

    broker_type = "qmt"

    def __init__(
        self,
        user_dir: str = "",
        account_id: str = "",
    ):
        self._user_dir = user_dir or os.environ.get("QMT_USER_DIR", "")
        self._account_id = account_id or os.environ.get("QMT_ACCOUNT_ID", "")
        self._state = BrokerState(
            connection=BrokerConnectionState.DISCONNECTED,
            broker_type="qmt",
        )
        self._xt_trader = None  # XtQuantTrader instance
        self._xt_acc = None     # XtQuantAccount instance

    # ── Lifecycle ──────────────────────────────────────────────────

    async def connect(self) -> BrokerState:
        """Connect to the QMT client via local xtquant API.

        QMT runs as a local process; xtquant connects via IPC (shared memory / TCP).
        The QMT client must be running and logged in before calling this.
        """
        if not self._user_dir:
            raise BrokerError(
                "QMT_USER_DIR not configured. Set it in .env or pass to constructor.",
                code="QMT_NO_USER_DIR",
            )

        if not Path(self._user_dir).exists():
            raise BrokerError(
                f"QMT user directory not found: {self._user_dir}",
                code="QMT_DIR_NOT_FOUND",
            )

        if not self._account_id:
            raise BrokerError(
                "QMT_ACCOUNT_ID not configured.",
                code="QMT_NO_ACCOUNT",
            )

        loop = asyncio.get_running_loop()

        def _do_connect():
            """Run blocking QMT API calls in thread pool."""
            try:
                from xtquant import XtQuantTrader, XtQuantTraderCallback
                from xtquant.xttype import XtAccount
            except ImportError:
                raise BrokerError(
                    "xtquant package not installed. Run: pip install xtquant\n"
                    "Or copy xtquant/ from your QMT installation directory.",
                    code="QMT_NO_XTQUANT",
                )

            # QMT session ID: random integer, used to distinguish sessions
            session_id = int(datetime.datetime.now().timestamp()) % 1000000

            # Determine QMT path
            qmt_path = str(Path(self._user_dir))

            # Create trader instance
            xt_trader = XtQuantTrader(qmt_path, session_id)

            # Register callback
            class _QmtCallback(XtQuantTraderCallback):
                def __init__(self, broker):
                    self.broker = broker

                def on_disconnected(self):
                    logger.warning("[QMT] Disconnected from client")
                    self.broker._state.connection = BrokerConnectionState.DISCONNECTED

                def on_stock_order(self, order):
                    logger.info(f"[QMT] Order update: {order.order_id} status={order.order_status}")

                def on_stock_trade(self, trade):
                    logger.info(f"[QMT] Trade: {trade.order_id} {trade.stock_code} "
                                f"{trade.trade_type} {trade.trade_volume}@{trade.trade_price}")

                def on_account_status(self, status):
                    logger.info(f"[QMT] Account status: {status.account_id} "
                                f"assets={status.m_dTotalAsset}")

            callback = _QmtCallback(self)
            xt_trader.register_callback(callback)

            # Start connection (blocks briefly)
            xt_trader.start()

            # Connect account
            connect_result = xt_trader.connect()
            if connect_result != 0:
                raise BrokerError(
                    f"QMT connection failed with code {connect_result}. "
                    f"Is QMT client running and logged in?",
                    code="QMT_CONNECT_FAILED",
                )

            # Subscribe to account updates
            from xtquant.xttype import XtAccount
            xt_acc = XtAccount(str(self._account_id), XtAccount.STOCK_ACCOUNT)
            subscribe_result = xt_trader.subscribe(xt_acc)
            if subscribe_result != 0:
                logger.warning(f"[QMT] Account subscribe returned {subscribe_result}")

            return xt_trader, xt_acc

        try:
            self._xt_trader, self._xt_acc = await loop.run_in_executor(
                None, _do_connect
            )
            self._state.connection = BrokerConnectionState.CONNECTED
            self._state.last_heartbeat = datetime.datetime.now()
            logger.info(f"[QMT] Connected to account {self._account_id}")
        except BrokerError:
            raise
        except Exception as e:
            self._state.connection = BrokerConnectionState.ERROR
            self._state.error_message = str(e)
            raise BrokerError(f"QMT connection failed: {e}", code="QMT_UNKNOWN")

        return self._state

    async def disconnect(self) -> None:
        if self._xt_trader:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._xt_trader.stop)
            self._xt_trader = None
        self._state.connection = BrokerConnectionState.DISCONNECTED

    def get_state(self) -> BrokerState:
        return self._state

    # ── Order operations ───────────────────────────────────────────

    async def submit_order(self, req: OrderRequest) -> OrderResult:
        """Submit an order to QMT.

        Maps our internal symbol format (000001.SZ) to QMT format (000001.SZ — same).
        Quantity is in shares (股) for stocks, contracts (张) for options.
        """
        if not self._xt_trader:
            raise BrokerError("Not connected", code="QMT_NOT_CONNECTED")

        loop = asyncio.get_running_loop()

        def _do_order():
            from xtquant.xttype import StockOrder

            # Build order
            # QMT price types:
            #   -1 = market price (市价)
            #   具体价格 = limit price
            price_type = (
                -1  # market order
                if req.order_type == OrderType.MARKET or req.price <= 0
                else req.price
            )

            # QMT order type constants:
            #   xtconstant.STOCK_BUY / STOCK_SELL
            from xtquant import xtconstant

            order = StockOrder()
            order.account = self._xt_acc
            order.stock_code = req.symbol  # QMT uses same format: "000001.SZ"
            order.order_type = (
                xtconstant.STOCK_BUY if req.side == OrderSide.BUY
                else xtconstant.STOCK_SELL
            )
            order.price_type = price_type
            order.price = req.price if req.price > 0 else 0
            order.order_volume = int(req.quantity)  # QMT requires integer
            order.strategy_name = f"strategy_{req.strategy_id}" if req.strategy_id else "manual"
            order.order_remark = req.remark

            # Submit to QMT
            seq = self._xt_trader.order(order)
            if seq < 0:
                raise BrokerError(
                    f"QMT order rejected (seq={seq}). Check: "
                    f"1) Trading hours  2) Price limits  3) Sufficient funds/position",
                    code="QMT_ORDER_REJECTED",
                )

            # Return immediate result (actual fill status comes via callback)
            return OrderResult(
                broker_order_id=str(seq),
                symbol=req.symbol,
                side=req.side,
                order_type=req.order_type,
                price=req.price,
                quantity=req.quantity,
                filled_quantity=0,  # not yet filled
                status=OrderStatus.SUBMITTED,
            )

        try:
            return await loop.run_in_executor(None, _do_order)
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f"QMT order failed: {e}", code="QMT_ORDER_ERROR")

    async def cancel_order(self, broker_order_id: str, symbol: str) -> OrderResult:
        if not self._xt_trader:
            raise BrokerError("Not connected", code="QMT_NOT_CONNECTED")

        loop = asyncio.get_running_loop()

        def _do_cancel():
            seq = int(broker_order_id)
            result = self._xt_trader.cancel_order(seq)
            if result != 0:
                raise BrokerError(
                    f"QMT cancel failed (code={result})",
                    code="QMT_CANCEL_FAILED",
                )
            return OrderResult(
                broker_order_id=broker_order_id,
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                price=0,
                quantity=0,
                status=OrderStatus.CANCELLED,
            )

        return await loop.run_in_executor(None, _do_cancel)

    async def query_order(self, broker_order_id: str) -> OrderResult:
        if not self._xt_trader:
            raise BrokerError("Not connected", code="QMT_NOT_CONNECTED")

        loop = asyncio.get_running_loop()

        def _do_query():
            seq = int(broker_order_id)
            orders = self._xt_trader.query_stock_orders(self._xt_acc, seq)
            if not orders:
                raise BrokerError(f"Order {broker_order_id} not found", code="QMT_ORDER_NOT_FOUND")
            o = orders[0]

            # Map QMT status to our OrderStatus
            status_map = {
                48: OrderStatus.SUBMITTED,      # 未报
                49: OrderStatus.SUBMITTED,      # 待报
                50: OrderStatus.FILLED,         # 已成
                51: OrderStatus.PARTIALLY_FILLED,  # 部成
                52: OrderStatus.CANCELLED,      # 已撤
                53: OrderStatus.FILLED,         # 部成已撤
                54: OrderStatus.REJECTED,       # 废单
            }

            return OrderResult(
                broker_order_id=str(o.order_id),
                symbol=o.stock_code,
                side=OrderSide.BUY if o.order_type in (23, 24) else OrderSide.SELL,
                order_type=OrderType.LIMIT,
                price=o.price,
                quantity=o.order_volume,
                filled_quantity=o.traded_volume,
                status=status_map.get(o.order_status, OrderStatus.SUBMITTED),
                commission=getattr(o, 'commission', 0.0),
                raw_response=o.__dict__ if hasattr(o, '__dict__') else {},
            )

        return await loop.run_in_executor(None, _do_query)

    # ── Position & Account ─────────────────────────────────────────

    async def get_positions(self) -> list[PositionInfo]:
        """Fetch real positions from QMT."""
        if not self._xt_trader:
            return []

        loop = asyncio.get_running_loop()

        def _do_query():
            positions = self._xt_trader.query_stock_positions(self._xt_acc)
            result = []
            for pos in positions:
                result.append(PositionInfo(
                    symbol=pos.stock_code,
                    quantity=pos.volume,
                    available_quantity=pos.can_use_volume,
                    avg_cost=pos.avg_price,
                    current_price=pos.market_value / pos.volume if pos.volume > 0 else 0,
                    market_value=pos.market_value,
                ))
            return result

        return await loop.run_in_executor(None, _do_query)

    async def get_account(self) -> AccountInfo:
        """Fetch real account info from QMT."""
        if not self._xt_trader:
            return AccountInfo()

        loop = asyncio.get_running_loop()

        def _do_query():
            assets = self._xt_trader.query_stock_asset(self._xt_acc)
            if not assets:
                return AccountInfo()

            return AccountInfo(
                account_id=str(self._account_id),
                total_assets=assets.total_asset,
                available_cash=assets.cash,
                frozen_cash=assets.frozen_cash,
                market_value=assets.market_value,
                total_pnl=assets.total_pnl,
            )

        return await loop.run_in_executor(None, _do_query)

    # ── Market Data (QMT provides Level-1 data) ────────────────────

    async def get_realtime_quote(self, symbol: str) -> dict:
        """Get real-time quote from QMT's market data feed.

        QMT provides direct exchange data with lower latency than
        the Tencent web API used by DataEngine.
        """
        if not self._xt_trader:
            # Fall back to Tencent API
            return await super().get_realtime_quote(symbol)

        loop = asyncio.get_running_loop()

        def _do_query():
            from xtquant import xtdata
            # QMT market data: download if needed, then get
            xtdata.download_history_data(symbol, period="1d", start_time="")
            data = xtdata.get_market_data(
                field_list=["lastPrice", "open", "high", "low", "lastClose", "volume"],
                stock_list=[symbol],
                period="tick",
                count=1,
            )
            # Parse into standard quote dict
            try:
                price = float(data["lastPrice"].iloc[-1, 0])
                pre_close = float(data["lastClose"].iloc[-1, 0])
                return {
                    "symbol": symbol,
                    "current_price": price,
                    "open": float(data["open"].iloc[-1, 0]),
                    "high": float(data["high"].iloc[-1, 0]),
                    "low": float(data["low"].iloc[-1, 0]),
                    "pre_close": pre_close,
                    "change": round(price - pre_close, 2),
                    "change_pct": round((price - pre_close) / pre_close * 100, 2) if pre_close else 0,
                    "volume": int(data["volume"].iloc[-1, 0]),
                    "data_source": "qmt",
                }
            except Exception:
                return {"symbol": symbol, "current_price": 0, "data_source": "qmt_error"}

        return await loop.run_in_executor(None, _do_query)
