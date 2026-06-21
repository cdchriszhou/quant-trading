"""Operation log model for audit trail."""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(64), default="")
    action = Column(String(128), nullable=False)  # login, create_strategy, update_strategy, place_order, etc.
    resource = Column(String(64), default="")  # The resource being operated on
    resource_id = Column(Integer, nullable=True)
    detail = Column(Text, default="")
    ip_address = Column(String(64), default="")
    status = Column(String(16), default="success")  # success, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
