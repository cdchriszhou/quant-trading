"""Schemas for notification endpoints."""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Any
from datetime import datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    title: str
    message: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    order_id: Optional[int] = None
    symbol: Optional[str] = None
    price: Optional[str] = None
    is_read: bool
    created_at: Optional[str] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_at_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat(timespec="seconds")
        return str(v)


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


class MarkReadRequest(BaseModel):
    ids: Optional[list[int]] = None  # None = mark all read
