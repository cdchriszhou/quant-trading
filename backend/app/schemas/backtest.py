"""Backtest schemas."""

from pydantic import BaseModel
from typing import Optional, Any


class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    strategy_type: str = "right_side_entry"
    parameters: dict = {}
    symbols: list = ["000001.SZ"]
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    commission_rate: float = 0.00025
    slippage: float = 0.001
    enable_env_filter: bool = True  # Layer 1: market environment filter
    enable_sector_filter: bool = True  # Layer 2: sector screening
    comparison_mode: bool = True  # Run with and without filters, compare
    optimize_params: bool = False  # Auto-optimize parameters


class BacktestOptimizeRequest(BaseModel):
    strategy_type: str = "right_side_entry"
    base_parameters: dict = {}
    symbols: list = ["000001.SZ"]
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    enable_env_filter: bool = True
    enable_sector_filter: bool = True
