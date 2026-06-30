"""Schemas for notification endpoints."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationOut(BaseModel):
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
    created_at: str

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


class MarkReadRequest(BaseModel):
    ids: Optional[list[int]] = None  # None = mark all read
