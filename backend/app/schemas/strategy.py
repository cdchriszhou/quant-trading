"""Strategy schemas."""

from pydantic import BaseModel, Field
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
<<<<<<< HEAD
    initial_capital: float = Field(100000.0, gt=0)
=======
    initial_capital: float = 1000000.0
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    symbols: Optional[list] = None
    time_frame: Optional[str] = None
    initial_capital: Optional[float] = Field(None, gt=0)
    status: Optional[str] = None
