"""Strategy schemas."""

from pydantic import BaseModel
from typing import Optional, Any


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    strategy_type: str = "ma"
    asset_type: str = "stock"
    symbols: list = []
    parameters: dict = {}
    time_frame: str = "1d"
    mode: str = "paper"
    initial_capital: float = 100000.0


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    symbols: Optional[list] = None
    time_frame: Optional[str] = None
    initial_capital: Optional[float] = None
    status: Optional[str] = None
