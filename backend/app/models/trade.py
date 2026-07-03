"""Trade model for recorded transactions."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.core.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    strategy_id = Column(Integer, nullable=True, index=True)
    order_id = Column(Integer, nullable=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(8), nullable=False)  # buy, sell
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # price * quantity
    commission = Column(Float, default=0.0)
    pnl = Column(Float, default=0.0)  # realized PnL for sell trades
    trade_mode = Column(String(16), default="paper")
    trade_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "amount": self.amount,
            "commission": self.commission,
            "pnl": self.pnl,
            "trade_mode": self.trade_mode,
            "trade_time": self.trade_time.isoformat() if self.trade_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
