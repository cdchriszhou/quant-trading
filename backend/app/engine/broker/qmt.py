"""MiniQMT / xtquant live broker adapter.

Requires:
  1. 安装并登录 MiniQMT / 投研端
  2. pip install xtquant（随 MiniQMT 提供）
  3. .env 配置 QMT_MINI_PATH / QMT_ACCOUNT_ID / ALLOW_LIVE_TRADING=true
"""

from __future__ import annotations

import time
from typing import Optional

from app.core.config import settings
from app.engine.broker.base import BrokerGateway, BrokerOrderResult, BrokerStatus


class QmtBroker(BrokerGateway):
    name = "qmt"

    def __init__(self):
        self._trader = None
        self._account = None
        self._session_id = int(time.time())
        self._last_error = ""

    def reset(self) -> None:
        """Drop live session so next call reconnects with fresh settings."""
        trader = self._trader
        self._trader = None
        self._account = None
        self._session_id = int(time.time())
        self._last_error = ""
        if trader is not None:
            try:
                stop = getattr(trader, "stop", None)
                if callable(stop):
                    stop()
            except Exception:
                pass

    def _ensure_connected(self) -> bool:
        if self._trader is not None and self._account is not None:
            return True
        if not settings.ALLOW_LIVE_TRADING:
            self._last_error = "ALLOW_LIVE_TRADING=false，已禁止实盘下单"
            return False
        if not settings.QMT_MINI_PATH or not settings.QMT_ACCOUNT_ID:
            self._last_error = "未配置 QMT_MINI_PATH / QMT_ACCOUNT_ID"
            return False
        try:
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
        except ImportError:
            self._last_error = "未安装 xtquant，请使用 MiniQMT 自带 Python 环境"
            return False

        try:
            trader = XtQuantTrader(settings.QMT_MINI_PATH, self._session_id)
            trader.start()
            acc = StockAccount(settings.QMT_ACCOUNT_ID)
            # connect may be sync/async depending on xtquant version
            connect = getattr(trader, "connect", None)
            if callable(connect):
                connect()
            self._trader = trader
            self._account = acc
            self._last_error = ""
            return True
        except Exception as e:
            self._last_error = f"QMT 连接失败: {e}"
            self._trader = None
            self._account = None
            return False

    def status(self, connect: bool = True) -> BrokerStatus:
        if connect:
            ok = self._ensure_connected()
        else:
            ok = self._trader is not None and self._account is not None
            if not settings.ALLOW_LIVE_TRADING:
                self._last_error = self._last_error or "ALLOW_LIVE_TRADING=false，已禁止实盘下单"
            elif not settings.QMT_MINI_PATH or not settings.QMT_ACCOUNT_ID:
                self._last_error = self._last_error or "未配置 QMT_MINI_PATH / QMT_ACCOUNT_ID"
            elif not ok and not self._last_error:
                self._last_error = "尚未连接，可点击「测试连接」"

        cash = None
        mv = None
        if ok and connect:
            try:
                cash = self.get_cash()
            except Exception as e:
                self._last_error = str(e)
                ok = False
        return BrokerStatus(
            broker="qmt",
            connected=ok,
            account_id=settings.QMT_ACCOUNT_ID or "",
            message=self._last_error or ("已连接 MiniQMT" if ok else "未连接"),
            cash=cash,
            market_value=mv,
            details={
                "mini_path": settings.QMT_MINI_PATH,
                "allow_live": settings.ALLOW_LIVE_TRADING,
            },
        )

    def get_cash(self) -> float:
        if not self._ensure_connected():
            raise RuntimeError(self._last_error or "QMT 未连接")
        # xtquant asset query — API varies by version
        query = getattr(self._trader, "query_stock_asset", None)
        if not callable(query):
            raise RuntimeError("当前 xtquant 版本不支持 query_stock_asset")
        asset = query(self._account)
        if asset is None:
            raise RuntimeError("无法查询资金账户")
        cash = getattr(asset, "cash", None)
        if cash is None:
            cash = getattr(asset, "m_dCash", 0)
        return float(cash or 0)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> BrokerOrderResult:
        if not self._ensure_connected():
            return BrokerOrderResult(success=False, message=self._last_error)

        try:
            from xtquant import xtconstant
        except ImportError:
            return BrokerOrderResult(success=False, message="xtquant 不可用")

        # Convert 000001.SZ → 000001.SZ (xtquant usually uses this form)
        code = symbol
        if side == "buy":
            order_code = xtconstant.STOCK_BUY
        else:
            order_code = xtconstant.STOCK_SELL

        price_type = xtconstant.FIX_PRICE
        if order_type == "market":
            # Fallback to latest price limit if market not supported
            price_type = getattr(xtconstant, "LATEST_PRICE", xtconstant.FIX_PRICE)
            order_price = price or -1
        else:
            order_price = float(price or 0)
            if order_price <= 0:
                return BrokerOrderResult(success=False, message="限价单需要有效价格")

        try:
            oid = self._trader.order_stock(
                self._account,
                code,
                order_code,
                int(quantity),
                price_type,
                order_price,
                "quant-trading",
                "web",
            )
            if oid is None or oid < 0:
                return BrokerOrderResult(
                    success=False,
                    message=f"QMT 拒单，返回码={oid}",
                )
            return BrokerOrderResult(
                success=True,
                broker_order_id=str(oid),
                status="submitted",
                filled_price=None,
                filled_quantity=None,
                message="已提交至 MiniQMT，等待成交回报",
            )
        except Exception as e:
            return BrokerOrderResult(success=False, message=f"QMT 下单异常: {e}")

    def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        if not self._ensure_connected():
            return BrokerOrderResult(success=False, message=self._last_error)
        try:
            cancel = getattr(self._trader, "cancel_order_stock", None) or getattr(
                self._trader, "cancel_order", None
            )
            if not callable(cancel):
                return BrokerOrderResult(
                    success=False,
                    broker_order_id=str(broker_order_id),
                    message="当前 xtquant 版本无撤单接口",
                )
            try:
                rc = cancel(self._account, int(broker_order_id))
            except TypeError:
                rc = cancel(int(broker_order_id))
            ok = rc is None or rc == 0 or rc is True
            return BrokerOrderResult(
                success=bool(ok),
                broker_order_id=str(broker_order_id),
                status="cancelled" if ok else "submitted",
                message="已提交撤单" if ok else f"撤单返回: {rc}",
            )
        except Exception as e:
            return BrokerOrderResult(
                success=False,
                broker_order_id=str(broker_order_id),
                message=f"QMT 撤单异常: {e}",
            )

    def query_order(self, broker_order_id: str) -> BrokerOrderResult:
        if not self._ensure_connected():
            return BrokerOrderResult(success=False, message=self._last_error)
        try:
            query = getattr(self._trader, "query_stock_orders", None)
            if not callable(query):
                return BrokerOrderResult(
                    success=False,
                    broker_order_id=str(broker_order_id),
                    status="unknown",
                    message="当前 xtquant 版本无订单查询接口",
                )
            rows = query(self._account) or []
            target = str(broker_order_id)
            for row in rows:
                oid = str(
                    getattr(row, "order_id", None)
                    or getattr(row, "m_strOrderSysID", None)
                    or getattr(row, "order_sysid", "")
                )
                if oid != target:
                    continue
                status_raw = str(
                    getattr(row, "order_status", None)
                    or getattr(row, "m_nOrderStatus", "")
                    or ""
                ).lower()
                filled_qty = float(
                    getattr(row, "traded_volume", None)
                    or getattr(row, "m_nVolumeTraded", 0)
                    or 0
                )
                filled_price = float(
                    getattr(row, "traded_price", None)
                    or getattr(row, "m_dPriceTraded", 0)
                    or 0
                )
                if filled_qty > 0 and ("fill" in status_raw or status_raw in ("3", "5", "filled", "全部成交")):
                    return BrokerOrderResult(
                        success=True,
                        broker_order_id=target,
                        status="filled",
                        filled_price=filled_price or None,
                        filled_quantity=filled_qty,
                        message="券商已成交",
                    )
                if "cancel" in status_raw or status_raw in ("5", "6", "cancelled"):
                    return BrokerOrderResult(
                        success=True,
                        broker_order_id=target,
                        status="cancelled",
                        message="券商已撤单",
                    )
                return BrokerOrderResult(
                    success=True,
                    broker_order_id=target,
                    status="submitted",
                    message=f"券商状态: {status_raw or 'unknown'}",
                )
            return BrokerOrderResult(
                success=False,
                broker_order_id=target,
                status="unknown",
                message="未在券商委托列表中找到该订单",
            )
        except Exception as e:
            return BrokerOrderResult(
                success=False,
                broker_order_id=str(broker_order_id),
                status="unknown",
                message=f"QMT 查单异常: {e}",
            )
