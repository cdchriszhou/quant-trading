"""Risk control rule model."""

import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.core.database import Base


class RiskRule(Base):
    __tablename__ = "risk_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    rule_type = Column(String(32), nullable=False)  # order_amount, daily_loss, position_pct, total_position, drawdown
    operator = Column(String(8), default="le")  # gt, lt, ge, le, eq
    threshold = Column(Float, nullable=False)
    action = Column(String(16), default="warn")  # warn, block, pause_strategy
    is_enabled = Column(Boolean, default=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "rule_type": self.rule_type,
            "operator": self.operator,
            "threshold": self.threshold,
            "action": self.action,
            "is_enabled": self.is_enabled,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
