"""Backtest schemas."""

from pydantic import BaseModel
from typing import Optional, Any


class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    strategy_type: str = "ma"
    parameters: dict = {}
    symbols: list = ["000001.SZ"]
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 100000.0
    commission_rate: float = 0.00025
    slippage: float = 0.001
