"""Backtest schemas."""

<<<<<<< HEAD
from pydantic import BaseModel, Field
from typing import Optional, Any
=======
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional


def _default_end_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _default_start_date() -> str:
    # ~2 calendar years: enough for MA60 strategies + one bull/bear stretch
    return (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)


class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    strategy_type: str = "right_side_entry"
    parameters: dict = {}
    symbols: list = ["000001.SZ"]
<<<<<<< HEAD
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = Field(100000.0, gt=0)
    commission_rate: float = Field(0.00025, ge=0)
    slippage: float = Field(0.001, ge=0)
=======
    start_date: str = Field(default_factory=_default_start_date)
    end_date: str = Field(default_factory=_default_end_date)
    initial_capital: float = 1000000.0
    commission_rate: float = 0.00025
    slippage: float = 0.001
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    enable_env_filter: bool = True  # Layer 1: market environment filter
    enable_sector_filter: bool = False  # Skipped until historical sector ranks exist
    comparison_mode: bool = True  # Run with and without filters, compare
    optimize_params: bool = False  # Auto-optimize parameters


class BacktestOptimizeRequest(BaseModel):
    strategy_type: str = "right_side_entry"
    base_parameters: dict = {}
    symbols: list = ["000001.SZ"]
<<<<<<< HEAD
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = Field(100000.0, gt=0)
=======
    start_date: str = Field(default_factory=_default_start_date)
    end_date: str = Field(default_factory=_default_end_date)
    initial_capital: float = 1000000.0
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    enable_env_filter: bool = True
    enable_sector_filter: bool = False  # same as run: no historical ranks yet
