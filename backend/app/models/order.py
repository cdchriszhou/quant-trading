"""Order model for tracking buy/sell orders."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    strategy_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String(32), nullable=False)
    order_type = Column(String(16), default="market")  # market, limit
    side = Column(String(8), nullable=False)  # buy, sell
    price = Column(Float, nullable=True)  # limit price
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, default=0.0)
    status = Column(String(16), default="pending")  # pending, submitted, filled, cancelled, rejected
    commission = Column(Float, default=0.0)
    trade_mode = Column(String(16), default="paper")  # paper, live
    remark = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "order_type": self.order_type,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "status": self.status,
            "commission": self.commission,
            "trade_mode": self.trade_mode,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
