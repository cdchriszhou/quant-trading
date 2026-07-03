"""Notification model for trade signals and system alerts."""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Notification(Base):
    """User notification for trade signals, risk alerts, and system messages."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(32), nullable=False, index=True)
    # 类型: signal_buy / signal_sell / order_placed / order_filled
    #       risk_blocked / stop_loss / take_profit / system
    title = Column(String(256), nullable=False)
    message = Column(Text, nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    strategy_name = Column(String(128), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    symbol = Column(String(32), nullable=True)
    price = Column(String(32), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="notifications")
    strategy = relationship("Strategy", foreign_keys=[strategy_id])
    order = relationship("Order", foreign_keys=[order_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "price": self.price,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
