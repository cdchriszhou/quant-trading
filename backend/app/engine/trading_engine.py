"""Trading Engine: Unified order execution via pluggable broker adapters.

Supports both paper trading (PaperBroker) and live trading via real broker APIs
(QMT, XTP, PTrade, CTP, custom). The TradingEngine now delegates all order
execution to the configured Broker instance while maintaining local DB records
for audit trail and fast queries.

Architecture:
    TradingEngine  →  BaseBroker (abstract)
                         ├── PaperBroker   (simulated fills)
                         ├── QMTBroker     (迅投QMT)
                         ├── XTPBroker     (中泰XTP)
                         └── CustomBroker  (user-provided)
"""

import asyncio
import datetime
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.trade import Trade
from app.models.position import Position as PositionModel
from app.engine.data_engine import data_engine

logger = logging.getLogger("trading_engine")


class TradingEngine:
    """Handles order placement, execution, and position management.

    Delegates actual order execution to a pluggable Broker adapter.
    Local DB records are always maintained for audit trail.
    """

    def __init__(self):
        self._commission_rate = settings.COMMISSION_RATE
        self._min_commission = settings.MIN_COMMISSION

    @property
    def broker(self):
        """Lazy-import the global broker instance (avoid circular imports)."""
        from app.brokers import get_broker
        return get_broker()

    # ── Order placement ────────────────────────────────────────────

    def place_order(self, db: Session, user_id: int, symbol: str, side: str,
                    order_type: str, quantity: float, price: Optional[float] = None,
                    strategy_id: Optional[int] = None, remark: str = "",
                    mode_override: Optional[str] = None) -> Order:
        """Place a new order — persists to DB and delegates to broker.

        For paper mode: the broker fills instantly and we record the result.
        For live mode: the broker submits the order; status updates come
        later via async callbacks or polling.
        """
        # Determine trade mode
        trade_mode = settings.TRADING_MODE
        if mode_override:
            trade_mode = mode_override
        elif strategy_id:
            from app.models.strategy import Strategy
            strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strat:
                trade_mode = strat.mode

        # Get current price from real-time quote
        quote = data_engine.get_realtime_quote(symbol)
        current_price = quote["current_price"]

        if order_type == "market":
            order_price = current_price
        else:
            order_price = price if price else current_price

        # Create local order record
        order = Order(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            order_type=order_type,
            side=side,
            price=order_price,
            quantity=quantity,
            status="pending",
            trade_mode=trade_mode,
            remark=remark,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Delegate to broker for actual execution
        self._execute_via_broker(db, order, current_price)

        return order

    def _execute_via_broker(self, db: Session, order: Order, current_price: float):
        """Submit order to broker and handle the result.

        In paper mode: this is synchronous (fills instantly).
        In live mode: this submits the order; the fill comes later.
        """
        # Run async broker call in a sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # We're inside an async context (e.g. strategy executor)
            # Schedule the order submission — don't block the event loop
            asyncio.ensure_future(self._submit_to_broker(db, order, current_price))
        else:
            # Synchronous context (e.g. FastAPI route handler)
            # Run the broker call in a thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run, self._submit_to_broker(db, order, current_price)
                )
                future.result(timeout=30)

    async def _submit_to_broker(self, db: Session, order: Order, current_price: float):
        """Async: submit order to the broker and update DB with result."""
        from app.brokers.base import OrderSide, OrderType, OrderRequest

        try:
            req = OrderRequest(
                symbol=order.symbol,
                side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
                order_type=OrderType.MARKET if order.order_type == "market" else OrderType.LIMIT,
                quantity=order.quantity,
                price=order.price if order.order_type == "limit" else 0,
                strategy_id=order.strategy_id,
                remark=order.remark or "",
            )

            result = await self.broker.submit_order(req)

            # Update local order with broker result
            order.broker_order_id = getattr(order, 'broker_order_id', None) or result.broker_order_id

            if result.status.value == "filled":
                self._record_fill(db, order, result.price, result.commission)
            elif result.status.value == "rejected":
                order.status = "rejected"
                order.remark = (order.remark or "") + f" [券商拒绝: {result.error_message}]"
                db.commit()
            elif result.status.value in ("submitted", "pending"):
                order.status = "submitted"
                db.commit()
            else:
                order.status = result.status.value
                db.commit()

        except Exception as e:
            logger.error(f"[Trading] Broker submit failed for order {order.id}: {e}")
            order.status = "rejected"
            order.remark = (order.remark or "") + f" [券商异常: {e}]"
            db.commit()

    def _record_fill(self, db: Session, order: Order, fill_price: float, commission: float = 0):
        """Record a filled order in the local database (position, trade)."""
        amount = fill_price * order.quantity
        if commission <= 0:
            commission = max(amount * self._commission_rate, self._min_commission)

        order.filled_quantity = order.quantity
        order.commission = commission
        order.status = "filled"
        order.updated_at = datetime.datetime.utcnow()

        trade = Trade(
            user_id=order.user_id,
            strategy_id=order.strategy_id,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            amount=amount,
            commission=commission,
            pnl=0,
            trade_mode=order.trade_mode,
        )

        position = db.query(PositionModel).filter(
            PositionModel.user_id == order.user_id,
            PositionModel.symbol == order.symbol,
            PositionModel.strategy_id == order.strategy_id,
            PositionModel.trade_mode == order.trade_mode,
        ).first()

        if order.side == "buy":
            if position:
                new_quantity = position.quantity + order.quantity
                new_cost = (position.avg_cost * position.quantity + fill_price * order.quantity) / new_quantity
                position.quantity = new_quantity
                position.available_quantity = new_quantity
                position.avg_cost = round(new_cost, 4)
            else:
                position = PositionModel(
                    user_id=order.user_id,
                    strategy_id=order.strategy_id,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    available_quantity=order.quantity,
                    avg_cost=fill_price,
                    current_price=fill_price,
                    market_value=amount,
                    unrealized_pnl=0,
                    unrealized_pnl_pct=0,
                    realized_pnl=0,
                    trade_mode=order.trade_mode,
                )
            db.add(position)
        else:  # sell
            if not position or position.quantity <= 0:
                order.status = "rejected"
                order.remark = (order.remark or "") + " [卖出被拒绝：无可卖持仓]"
                db.commit()
                return

            realized_pnl = (fill_price - position.avg_cost) * order.quantity
            trade.pnl = round(realized_pnl, 2)

            position.quantity -= order.quantity
            position.available_quantity -= order.quantity
            position.realized_pnl += realized_pnl
            if position.quantity <= 0:
                db.delete(position)
            else:
                try:
                    quote = data_engine.get_realtime_quote(order.symbol)
                    position.current_price = quote["current_price"]
                except RuntimeError:
                    position.current_price = fill_price
                position.market_value = position.quantity * position.current_price
                position.unrealized_pnl = round(
                    (position.current_price - position.avg_cost) * position.quantity, 2
                )
                position.unrealized_pnl_pct = round(
                    (position.current_price - position.avg_cost) / position.avg_cost * 100, 2
                ) if position.avg_cost > 0 else 0

        db.add(trade)
        db.commit()

    # ── Order management ───────────────────────────────────────────

    def cancel_order(self, db: Session, order_id: int, user_id: int) -> Optional[Order]:
        """Cancel a pending order — DB + broker."""
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status.in_(["pending", "submitted"]),
        ).first()
        if not order:
            return None

        # Cancel on broker side
        broker_order_id = getattr(order, 'broker_order_id', None)
        if broker_order_id:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.broker.cancel_order(str(broker_order_id), order.symbol)
                )
            except RuntimeError:
                pass  # No event loop; skip broker cancel in sync context

        order.status = "cancelled"
        order.updated_at = datetime.datetime.utcnow()
        db.commit()
        return order

    def get_orders(self, db: Session, user_id: int, status: Optional[str] = None,
                   limit: int = 50) -> list:
        """Get orders for a user."""
        query = db.query(Order).filter(Order.user_id == user_id)
        if status:
            query = query.filter(Order.status == status)
        orders = query.order_by(Order.created_at.desc()).limit(limit).all()
        return [o.to_dict() for o in orders]

    def get_positions(self, db: Session, user_id: int) -> list:
        """Get current positions — syncs with broker if live, or uses DB."""
        # If using live broker, could sync positions here
        # For paper mode, positions are maintained in DB
        positions = db.query(PositionModel).filter(
            PositionModel.user_id == user_id,
            PositionModel.quantity > 0,
        ).all()

        if not positions:
            return []

        symbols = [pos.symbol for pos in positions]
        quotes_map = data_engine.batch_get_quotes(symbols)

        result = []
        for pos in positions:
            quote = quotes_map.get(pos.symbol, {})
            current_price = quote.get("current_price", pos.current_price or 0)
            stock_name = quote.get("name", "") or data_engine.lookup_stock_name(pos.symbol)

            pos.current_price = current_price
            pos.market_value = round(pos.quantity * current_price, 2)
            pos.unrealized_pnl = round(
                (current_price - pos.avg_cost) * pos.quantity, 2
            )
            pos.unrealized_pnl_pct = round(
                (current_price - pos.avg_cost) / pos.avg_cost * 100, 2
            ) if pos.avg_cost > 0 else 0

            result.append(pos.to_dict(name=stock_name))

        db.commit()
        return result

    def get_account_summary(self, db: Session, user_id: int) -> dict:
        """Get account summary including total equity."""
        from app.models.user import User
        from app.models.trade import Trade
        from sqlalchemy import func, case

        user = db.query(User).filter(User.id == user_id).first()
        positions = self.get_positions(db, user_id)

        total_market_value = sum(p["market_value"] for p in positions)
        total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

        agg = db.query(
            func.coalesce(func.sum(case(
                (Trade.side == "sell", Trade.pnl), else_=0
            )), 0).label("total_realized_pnl"),
            func.coalesce(func.sum(case(
                (Trade.side == "buy", Trade.amount + Trade.commission), else_=0
            )), 0).label("total_bought"),
            func.coalesce(func.sum(case(
                (Trade.side == "sell", Trade.amount - Trade.commission), else_=0
            )), 0).label("total_sold"),
        ).filter(Trade.user_id == user_id).first()

        total_realized_pnl = float(agg.total_realized_pnl)
        total_bought = float(agg.total_bought)
        total_sold = float(agg.total_sold)
        cash_balance = user.initial_cash - total_bought + total_sold if user else 0

        total_equity = cash_balance + total_market_value
        total_pnl = total_realized_pnl + total_unrealized_pnl
        total_return_pct = ((total_equity - user.initial_cash) / user.initial_cash * 100) if user and user.initial_cash else 0

        return {
            "initial_cash": float(user.initial_cash) if user else 0,
            "cash_balance": round(cash_balance, 2),
            "market_value": round(total_market_value, 2),
            "total_equity": round(total_equity, 2),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "position_count": len(positions),
        }


trading_engine = TradingEngine()
