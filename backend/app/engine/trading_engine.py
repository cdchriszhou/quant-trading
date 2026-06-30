"""Trading Engine: Paper/live order execution and position management."""

import random
import datetime
import math
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.trade import Trade
from app.models.position import Position as PositionModel
from app.engine.data_engine import data_engine


class TradingEngine:
    """Handles order placement, execution, and position management."""

    def __init__(self):
        self.commission_rate = settings.COMMISSION_RATE
        self.min_commission = settings.MIN_COMMISSION

    def place_order(self, db: Session, user_id: int, symbol: str, side: str,
                    order_type: str, quantity: float, price: Optional[float] = None,
                    strategy_id: Optional[int] = None, remark: str = "",
                    mode_override: Optional[str] = None) -> Order:
        """Place a new order. Uses strategy mode if strategy_id provided."""
        # Determine trade mode
        trade_mode = settings.TRADING_MODE
        if mode_override:
            trade_mode = mode_override
        elif strategy_id:
            from app.models.strategy import Strategy
            strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strat:
                trade_mode = strat.mode

        # Get current price if market order
        quote = data_engine.get_realtime_quote(symbol)
        current_price = quote["current_price"]
        order_price = price if price else current_price

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

        # Auto-execute for market orders in paper mode
        if order_type == "market":
            self._execute_order(db, order, current_price)

        return order

    def _execute_order(self, db: Session, order: Order, execution_price: float):
        """Execute an order (fill it)."""
        # Calculate commission
        amount = execution_price * order.quantity
        commission = max(amount * self.commission_rate, self.min_commission)

        # Update order
        order.filled_quantity = order.quantity
        order.commission = commission
        order.status = "filled"
        order.updated_at = datetime.datetime.utcnow()

        # Create trade record
        trade = Trade(
            user_id=order.user_id,
            strategy_id=order.strategy_id,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=execution_price,
            quantity=order.quantity,
            amount=amount,
            commission=commission,
            pnl=0,
            trade_mode=order.trade_mode,
        )

        # Update position
        position = db.query(PositionModel).filter(
            PositionModel.user_id == order.user_id,
            PositionModel.symbol == order.symbol,
            PositionModel.strategy_id == order.strategy_id,
            PositionModel.trade_mode == order.trade_mode,
        ).first()

        if order.side == "buy":
            if position:
                # Update average cost
                new_quantity = position.quantity + order.quantity
                new_cost = (position.avg_cost * position.quantity +
                           execution_price * order.quantity) / new_quantity
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
                    avg_cost=execution_price,
                    current_price=execution_price,
                    market_value=amount,
                    unrealized_pnl=0,
                    unrealized_pnl_pct=0,
                    realized_pnl=0,
                    trade_mode=order.trade_mode,
                )
            db.add(position)
        else:  # sell
            if position:
                # Calculate realized PnL
                realized_pnl = (execution_price - position.avg_cost) * order.quantity
                trade.pnl = round(realized_pnl, 2)

                position.quantity -= order.quantity
                position.available_quantity -= order.quantity
                position.realized_pnl += realized_pnl
                if position.quantity <= 0:
                    db.delete(position)
                else:
                    position.current_price = execution_price
                    position.market_value = position.quantity * execution_price
                    position.unrealized_pnl = round(
                        (execution_price - position.avg_cost) * position.quantity, 2
                    )

        db.add(trade)
        db.commit()

    def cancel_order(self, db: Session, order_id: int, user_id: int) -> Optional[Order]:
        """Cancel a pending order."""
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status == "pending",
        ).first()
        if order:
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
        """Get current positions for a user."""
        positions = db.query(PositionModel).filter(
            PositionModel.user_id == user_id,
            PositionModel.quantity > 0,
        ).all()

        # Update current prices
        for pos in positions:
            quote = data_engine.get_realtime_quote(pos.symbol)
            pos.current_price = quote["current_price"]
            pos.market_value = round(pos.quantity * pos.current_price, 2)
            pos.unrealized_pnl = round(
                (pos.current_price - pos.avg_cost) * pos.quantity, 2
            )
            pos.unrealized_pnl_pct = round(
                (pos.current_price - pos.avg_cost) / pos.avg_cost * 100, 2
            ) if pos.avg_cost > 0 else 0

        db.commit()
        return [p.to_dict() for p in positions]

    def get_account_summary(self, db: Session, user_id: int) -> dict:
        """Get account summary including total equity."""
        from app.models.user import User
        from app.models.trade import Trade
        user = db.query(User).filter(User.id == user_id).first()
        positions = self.get_positions(db, user_id)

        total_market_value = sum(p["market_value"] for p in positions)
        total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

        # Realized PnL from Trade table (positions may be fully sold & deleted)
        realized_trades = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.side == "sell",
        ).all()
        total_realized_pnl = sum(t.pnl for t in realized_trades)

        # Calculate available cash from trades
        trades = db.query(Trade).filter(Trade.user_id == user_id).all()
        total_bought = sum(t.amount + t.commission for t in trades if t.side == "buy")
        total_sold = sum(t.amount - t.commission for t in trades if t.side == "sell")
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
