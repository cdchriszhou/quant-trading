"""Market environment API schemas."""

from pydantic import BaseModel
from typing import Optional


class MarketEnvStatus(BaseModel):
    """Current market environment status."""
    env_state: str  # "bull" | "bear" | "neutral"
    avg_price: float = 0.0
    ma20: float = 0.0
    ma20_slope: float = 0.0
    signals: list = []
    warnings: list = []
    can_trade: bool = False
    message: str = ""


class MarketEnvHistoryQuery(BaseModel):
    """Query params for historical env records."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 60
