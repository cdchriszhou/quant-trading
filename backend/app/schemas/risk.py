"""Risk rule schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class RiskRuleCreate(BaseModel):
    name: str
    rule_type: str
    operator: str = "le"
    threshold: float
    action: str = "warn"
    description: str = ""
    is_enabled: bool = True


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    action: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class RiskCheckRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0)
    amount: float = Field(..., ge=0)
