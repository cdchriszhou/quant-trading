"""Strategy Engine: Built-in strategy implementations and execution."""

import math
import numpy as np
import pandas as pd
from typing import Callable, Optional


class StrategyEngine:
    """Lightweight strategy engine that calculates trading signals."""

    def __init__(self):
        self.strategies = {
            "ma": self._ma_strategy,
            "macd": self._macd_strategy,
            "bollinger": self._bollinger_strategy,
            "grid": self._grid_strategy,
            "dca": self._dca_strategy,
        }
        self._default_params = {
            "ma": {"fast_period": 5, "slow_period": 20, "signal_type": "cross"},
            "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "bollinger": {"period": 20, "std_dev": 2.0, "oversold_threshold": -2, "overbought_threshold": 2},
            "grid": {"grid_levels": 10, "grid_spacing_pct": 1.0, "base_price": 0},
            "dca": {"interval_days": 7, "fixed_amount": 1000, "target_symbols": []},
        }

    def get_supported_strategies(self) -> list:
        """Get list of supported strategy types with descriptions."""
        return [
            {"type": "ma", "name": "均线策略", "description": "基于快慢均线交叉的交易策略"},
            {"type": "macd", "name": "MACD策略", "description": "基于MACD指标金叉死叉信号的交易策略"},
            {"type": "bollinger", "name": "布林带策略", "description": "基于布林带上下轨的超买超卖策略"},
            {"type": "grid", "name": "网格交易", "description": "在价格区间内网格化挂单交易"},
            {"type": "dca", "name": "定投策略", "description": "定期定额投资策略"},
        ]

    def get_default_params(self, strategy_type: str) -> dict:
        """Get default parameters for a strategy type."""
        return self._default_params.get(strategy_type, {})

    def calculate_signals(self, strategy_type: str, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Calculate trading signals for given data and strategy."""
        strategy_func = self.strategies.get(strategy_type)
        if strategy_func is None:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        return strategy_func(df, params)

    def _ma_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Moving Average Crossover strategy."""
        result = df.copy()
        fast_period = int(params.get("fast_period", 5))
        slow_period = int(params.get("slow_period", 20))
        signal_type = params.get("signal_type", "cross")

        result["ma_fast"] = result["close"].rolling(window=fast_period).mean()
        result["ma_slow"] = result["close"].rolling(window=slow_period).mean()
        result["ma_diff"] = result["ma_fast"] - result["ma_slow"]

        if signal_type == "cross":
            result["signal"] = 0
            result.loc[result["ma_fast"] > result["ma_slow"], "signal"] = 1
            result.loc[result["ma_fast"] <= result["ma_slow"], "signal"] = -1
            # Generate buy/sell signals on cross
            result["buy_signal"] = ((result["signal"] == 1) & (result["signal"].shift(1) == -1))
            result["sell_signal"] = ((result["signal"] == -1) & (result["signal"].shift(1) == 1))
        else:
            result["buy_signal"] = False
            result["sell_signal"] = False

        result["signal_strength"] = 0.0
        result.loc[result["buy_signal"], "signal_strength"] = 1.0
        result.loc[result["sell_signal"], "signal_strength"] = -1.0
        return result

    def _macd_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """MACD strategy."""
        result = df.copy()
        fast = int(params.get("fast_period", 12))
        slow = int(params.get("slow_period", 26))
        signal = int(params.get("signal_period", 9))

        result["ema_fast"] = result["close"].ewm(span=fast, adjust=False).mean()
        result["ema_slow"] = result["close"].ewm(span=slow, adjust=False).mean()
        result["macd_line"] = result["ema_fast"] - result["ema_slow"]
        result["macd_signal"] = result["macd_line"].ewm(span=signal, adjust=False).mean()
        result["macd_histogram"] = result["macd_line"] - result["macd_signal"]

        result["buy_signal"] = (
            (result["macd_line"] > result["macd_signal"]) &
            (result["macd_line"].shift(1) <= result["macd_signal"].shift(1))
        )
        result["sell_signal"] = (
            (result["macd_line"] < result["macd_signal"]) &
            (result["macd_line"].shift(1) >= result["macd_signal"].shift(1))
        )
        result["signal_strength"] = result["macd_histogram"] / result["close"] * 100
        return result

    def _bollinger_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Bollinger Bands strategy."""
        result = df.copy()
        period = int(params.get("period", 20))
        std_dev = float(params.get("std_dev", 2.0))

        result["bb_middle"] = result["close"].rolling(window=period).mean()
        result["bb_std"] = result["close"].rolling(window=period).std()
        result["bb_upper"] = result["bb_middle"] + std_dev * result["bb_std"]
        result["bb_lower"] = result["bb_middle"] - std_dev * result["bb_std"]
        result["bb_width"] = (result["bb_upper"] - result["bb_lower"]) / result["bb_middle"] * 100
        result["bb_position"] = (result["close"] - result["bb_lower"]) / (result["bb_upper"] - result["bb_lower"])

        result["buy_signal"] = result["close"] < result["bb_lower"]
        result["sell_signal"] = result["close"] > result["bb_upper"]
        result["signal_strength"] = result.apply(
            lambda r: (r["bb_lower"] - r["close"]) / r["bb_lower"] * 100
            if r["close"] < r["bb_lower"]
            else (r["bb_upper"] - r["close"]) / r["bb_upper"] * 100
            if r["close"] > r["bb_upper"]
            else 0, axis=1
        )
        # Normalize signal_strength
        result["signal_strength"] = result["signal_strength"].clip(-5, 5)
        return result

    def _grid_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Grid trading strategy."""
        result = df.copy()
        grid_levels = int(params.get("grid_levels", 10))
        grid_spacing_pct = float(params.get("grid_spacing_pct", 1.0))
        base_price = float(params.get("base_price", df["close"].iloc[0]))

        grid_prices = [
            base_price * (1 + grid_spacing_pct / 100 * (i - grid_levels / 2))
            for i in range(grid_levels + 1)
        ]
        result["buy_signal"] = result["close"].apply(
            lambda x: any(abs(x - gp) / gp < 0.001 for gp in grid_prices[:len(grid_prices)//2])
        )
        result["sell_signal"] = result["close"].apply(
            lambda x: any(abs(x - gp) / gp < 0.001 for gp in grid_prices[len(grid_prices)//2:])
        )
        result["signal_strength"] = 0.0
        return result

    def _dca_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Dollar Cost Averaging strategy."""
        result = df.copy()
        interval_days = int(params.get("interval_days", 7))
        fixed_amount = float(params.get("fixed_amount", 1000))

        result["buy_signal"] = False
        result["sell_signal"] = False
        result["signal_strength"] = 0.0

        # Buy on a fixed schedule
        for i in range(len(result)):
            if i % interval_days == 0:
                result.loc[result.index[i], "buy_signal"] = True
                result.loc[result.index[i], "signal_strength"] = 1.0
        return result


strategy_engine = StrategyEngine()
