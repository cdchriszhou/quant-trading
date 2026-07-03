"""Paper Trading Broker — simulated order execution and position management.

This is the default broker. It simulates fills instantly for market orders
and tracks positions / PnL in the local database, exactly as the original
TradingEngine did before the broker abstraction was introduced.
"""

import asyncio
import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.brokers.base import (
    BaseBroker, BrokerError, BrokerState, BrokerConnectionState,
    OrderSide, OrderType, OrderStatus,
    OrderRequest, OrderResult, PositionInfo, AccountInfo,
)


class PaperBroker(BaseBroker):
    """Simulated trading — fills market orders instantly at last price.

    Uses the application database for persistence. Does NOT connect to
    any external system; connect() / disconnect() are no-ops.
    """

    broker_type = "paper"

    def __init__(self, commission_rate: float = 0.00025, min_commission: float = 5.0):
        self._commission_rate = commission_rate
        self._min_commission = min_commission
        self._state = BrokerState(
            connection=BrokerConnectionState.DISCONNECTED,
            broker_type="paper",
        )
        self._order_counter = 0

    # ── Lifecycle ──────────────────────────────────────────────────

    async def connect(self) -> BrokerState:
        self._state.connection = BrokerConnectionState.CONNECTED
        self._state.last_heartbeat = datetime.datetime.now()
        return self._state

    async def disconnect(self) -> None:
        self._state.connection = BrokerConnectionState.DISCONNECTED

    def get_state(self) -> BrokerState:
        return self._state

    # ── Order submission ───────────────────────────────────────────

    async def submit_order(self, req: OrderRequest) -> OrderResult:
        """Simulate order fill at the current market price.

        Market orders fill instantly at the last quote price.
        Limit orders are simulated as market orders in paper mode (always fill).
        """
        # Get current price from market data
        try:
            from app.engine.data_engine import data_engine
            quote = data_engine.get_realtime_quote(req.symbol)
            fill_price = quote["current_price"]
        except Exception:
            fill_price = req.price if req.price > 0 else 10.0

        if fill_price <= 0:
            fill_price = req.price if req.price > 0 else 10.0

        # For limit orders in paper mode, use the limit price if market is better
        if req.order_type == OrderType.LIMIT and req.price > 0:
            if req.side == OrderSide.BUY:
                fill_price = min(fill_price, req.price)
            else:
                fill_price = max(fill_price, req.price)

        self._order_counter += 1
        broker_id = f"PAPER_{datetime.datetime.now().strftime('%Y%m%d')}_{self._order_counter:06d}"

        # Calculate commission
        amount = fill_price * req.quantity
        commission = max(amount * self._commission_rate, self._min_commission)

        return OrderResult(
            broker_order_id=broker_id,
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            price=fill_price,
            quantity=req.quantity,
            filled_quantity=req.quantity,
            status=OrderStatus.FILLED,
            commission=round(commission, 2),
        )

    async def cancel_order(self, broker_order_id: str, symbol: str) -> OrderResult:
        return OrderResult(
            broker_order_id=broker_order_id,
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=0,
            quantity=0,
            status=OrderStatus.CANCELLED,
        )

    async def query_order(self, broker_order_id: str) -> OrderResult:
        return OrderResult(
            broker_order_id=broker_order_id,
            symbol="",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=0,
            quantity=0,
            status=OrderStatus.FILLED,
        )

    # ── Position & Account ─────────────────────────────────────────

    async def get_positions(self) -> list[PositionInfo]:
        """Return positions from the local database (not from a broker)."""
        # Paper mode reads positions from DB via TradingEngine.get_positions()
        return []

    async def get_account(self) -> AccountInfo:
        # Paper mode reads account from DB via TradingEngine.get_account_summary()
        return AccountInfo()
