"""Trading schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class OrderCreate(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "market"
    price: Optional[float] = Field(None, ge=0)
    quantity: float = Field(..., gt=0)
    strategy_id: Optional[int] = None
    remark: Optional[str] = ""
    mode: Optional[Literal["paper", "live"]] = None


class OrderCancel(BaseModel):
    order_id: int
