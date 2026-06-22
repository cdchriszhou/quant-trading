"""Trading schemas."""

from pydantic import BaseModel
from typing import Optional


class OrderCreate(BaseModel):
    symbol: str
    side: str  # buy, sell
    order_type: str = "market"  # market, limit
    price: Optional[float] = None
    quantity: float
    strategy_id: Optional[int] = None
    remark: Optional[str] = ""
    mode: Optional[str] = None  # paper, live (overrides global config)


class OrderCancel(BaseModel):
    order_id: int
