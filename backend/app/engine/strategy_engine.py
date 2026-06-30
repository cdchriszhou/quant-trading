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
            "dragon_pullback": self._dragon_pullback_strategy,
            "trend_following": self._trend_following_strategy,
            "right_side_entry": self._right_side_entry_strategy,
        }
        self._default_params = {
            "ma": {"fast_period": 5, "slow_period": 20, "signal_type": "cross"},
            "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "bollinger": {"period": 20, "std_dev": 2.0, "oversold_threshold": -2, "overbought_threshold": 2},
            "grid": {"grid_levels": 10, "grid_spacing_pct": 1.0, "base_price": 0},
            "dca": {"interval_days": 7, "fixed_amount": 1000, "target_symbols": []},
            "dragon_pullback": {
                # ── 强势识别参数（规则3）──
                "strong_lookback": 10,         # 强势识别回溯天数
                "limit_up_threshold": 9.5,     # 涨停阈值(%)
                "min_limit_ups": 2,            # 最少涨停次数（连板型）
                "breakout_gain_pct": 5.0,      # 突破型：当日最小涨幅(%)
                "breakout_high_period": 60,    # 突破型：创新高回溯天数
                "breakout_vol_ratio": 1.5,     # 突破型：成交量放大倍数
                # ── 均线多头参数（规则4）──
                "ma_short": 5,                 # 短期均线
                "ma_medium": 10,               # 中期均线
                "ma_long": 20,                 # 长期均线
                "ma_trend": 60,                # 趋势均线
                # ── 回调验证参数（规则5-7）──
                "min_pullback_days": 2,        # 最小回调天数
                "max_pullback_days": 8,        # 最大回调天数
                "fib_ratio_strong": 0.382,     # 极强股黄金分割位
                "fib_ratio_normal": 0.5,       # 强势股回调位
                "vol_contraction_ratio": 0.5,  # 缩量标准：回调量 < 主升浪最大量 * ratio
                "max_bearish_body_pct": 4.0,   # 回调阴线实体最大幅度(%)
                "max_single_drop_pct": 5.0,    # 单日最大跌幅(%)
                # ── 买入参数（规则8）──
                "entry_near_ma": True,         # 触及20日均线时买入
                "entry_near_fib": True,        # 触及斐波那契位时买入
                "entry_tolerance_pct": 2.0,    # 入场容忍度(%)
                # ── 止损参数（规则9-10）──
                "stop_loss_pct": 5.0,          # 空间止损(%)
                "ma_stop_buffer_pct": 2.0,     # 均线止损缓冲(%)
                "max_capital_loss_pct": 2.0,   # 单笔最大资金亏损(%)
                "time_stop_days_1": 5,         # 时间止损1：N天后未盈利3%减仓
                "time_stop_profit_1": 3.0,     # 时间止损1盈利要求(%)
                "time_stop_days_2": 8,         # 时间止损2：N天后未创新高清仓
                # ── 止盈参数（规则11-12）──
                "trail_profit_level_1": 10.0,  # 移动止盈级别1：盈利>N%止损移至成本
                "trail_profit_level_2": 20.0,  # 移动止盈级别2：盈利>N%跌破MA5卖50%
                "top_vol_surge_ratio": 1.0,    # 天量标准：成交量创N日新高
                "top_gain_stall_pct": 2.0,     # 放量滞涨标准(%)
                "top_turnover_rate": 15.0,     # 换手率警戒(%)
                "top_big_drop_pct": 5.0,       # 长阴破位跌幅(%)
                "top_deviation_pct": 30.0,     # 乖离率过大(%)
            },
            "trend_following": {
                "ma_short": 5,
                "ma_medium": 20,
                "ma_long": 60,
                "adx_period": 14,
                "adx_threshold": 25,
                "atr_period": 14,
                "atr_multiplier": 2.0,
                "trailing_stop_pct": 8.0,
                "volume_confirm_ratio": 1.2,
            },
            "right_side_entry": {
                "ma_short": 5,
                "ma_medium": 20,
                "ma_long": 60,
                "pullback_near_ma_pct": 2.0,
                "vol_contraction_ratio": 0.5,
                "vol_expansion_ratio": 1.5,
                "ma_slope_flat_threshold": 0.001,
                "stop_loss_ma_break_pct": 2.0,
                "hard_stop_pct": 7.0,
                "min_daily_amount": 50_000_000,
            },
        }

    def get_supported_strategies(self) -> list:
        """Get list of supported strategy types with descriptions."""
        return [
            {"type": "ma", "name": "均线策略", "description": "基于快慢均线交叉的交易策略"},
            {"type": "macd", "name": "MACD策略", "description": "基于MACD指标金叉死叉信号的交易策略"},
            {"type": "bollinger", "name": "布林带策略", "description": "基于布林带上下轨的超买超卖策略"},
            {"type": "grid", "name": "网格交易", "description": "在价格区间内网格化挂单交易"},
            {"type": "dca", "name": "定投策略", "description": "定期定额投资策略"},
            {"type": "dragon_pullback", "name": "龙回头策略", "description": "强势股回调买入：识别涨停/突破后的缩量回调，在均线/斐波那契支撑位分批建仓，含硬止损+移动止盈+时间止损"},
            {"type": "trend_following", "name": "趋势跟踪策略", "description": "基于ADX+均线多头排列的趋势跟踪策略，结合ATR动态止损和成交量确认"},
            {"type": "right_side_entry", "name": "右侧入场策略", "description": "回踩20日线企稳+缩量止跌后放量阳线突破的趋势确认策略（纯右侧，不等最低点）。包含大盘环境过滤和行业板块筛选"},
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

    # ═══════════════════════════════════════════════════════════════
    # 均线策略
    # ═══════════════════════════════════════════════════════════════
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
            result["buy_signal"] = ((result["signal"] == 1) & (result["signal"].shift(1) == -1))
            result["sell_signal"] = ((result["signal"] == -1) & (result["signal"].shift(1) == 1))
        else:
            result["buy_signal"] = False
            result["sell_signal"] = False

        result["signal_strength"] = 0.0
        result.loc[result["buy_signal"], "signal_strength"] = 1.0
        result.loc[result["sell_signal"], "signal_strength"] = -1.0
        return result

    # ═══════════════════════════════════════════════════════════════
    # MACD策略
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    # 布林带策略
    # ═══════════════════════════════════════════════════════════════
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
        result["signal_strength"] = result["signal_strength"].clip(-5, 5)
        return result

    # ═══════════════════════════════════════════════════════════════
    # 网格交易
    # ═══════════════════════════════════════════════════════════════
    def _grid_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Grid trading strategy."""
        result = df.copy()
        grid_levels = int(params.get("grid_levels", 10))
        grid_spacing_pct = float(params.get("grid_spacing_pct", 1.0))
        base_price = float(params.get("base_price", 0)) or df["close"].iloc[0]
        if base_price <= 0 or grid_spacing_pct <= 0:
            result["buy_signal"] = False
            result["sell_signal"] = False
            result["signal_strength"] = 0.0
            return result

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

    # ═══════════════════════════════════════════════════════════════
    # 定投策略
    # ═══════════════════════════════════════════════════════════════
    def _dca_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Dollar Cost Averaging strategy."""
        result = df.copy()
        interval_days = int(params.get("interval_days", 7))
        fixed_amount = float(params.get("fixed_amount", 1000))

        result["buy_signal"] = False
        result["sell_signal"] = False
        result["signal_strength"] = 0.0

        for i in range(len(result)):
            if i % interval_days == 0:
                result.loc[result.index[i], "buy_signal"] = True
                result.loc[result.index[i], "signal_strength"] = 1.0
        return result

    # ═══════════════════════════════════════════════════════════════
    # 龙回头策略（强势股回调买入）— 规则1-12综合实现
    # ═══════════════════════════════════════════════════════════════
    def _dragon_pullback_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Dragon Pullback Strategy — 强势股回调战术体系.

        实现规则：
          规则3-4: 强势识别 + 均线多头
          规则5-7: 回调验证（时间、空间、量价）
          规则8:   分批买入（均线支撑/斐波那契支撑）
          规则9-10: 硬止损 + 时间止损
          规则11-12: 移动止盈 + 见顶信号
        """
        result = df.copy()
        n = len(result)
        if n < 60:
            result["buy_signal"] = False
            result["sell_signal"] = False
            result["signal_strength"] = 0.0
            return result

        # ── 参数提取 ──
        strong_lookback = int(params.get("strong_lookback", 10))
        limit_up_threshold = float(params.get("limit_up_threshold", 9.5)) / 100.0
        min_limit_ups = int(params.get("min_limit_ups", 2))
        breakout_gain = float(params.get("breakout_gain_pct", 5.0)) / 100.0
        breakout_high_period = int(params.get("breakout_high_period", 60))
        breakout_vol_ratio = float(params.get("breakout_vol_ratio", 1.5))

        ma_s = int(params.get("ma_short", 5))
        ma_m = int(params.get("ma_medium", 10))
        ma_l = int(params.get("ma_long", 20))
        ma_t = int(params.get("ma_trend", 60))

        min_pb_days = int(params.get("min_pullback_days", 2))
        max_pb_days = int(params.get("max_pullback_days", 8))
        fib_strong = float(params.get("fib_ratio_strong", 0.382))
        fib_normal = float(params.get("fib_ratio_normal", 0.5))
        vol_contract = float(params.get("vol_contraction_ratio", 0.5))

        stop_loss = float(params.get("stop_loss_pct", 5.0)) / 100.0
        ma_stop_buf = float(params.get("ma_stop_buffer_pct", 2.0)) / 100.0

        trail_1 = float(params.get("trail_profit_level_1", 10.0)) / 100.0
        trail_2 = float(params.get("trail_profit_level_2", 20.0)) / 100.0

        # ── 计算均线 ──
        result["ma5"] = result["close"].rolling(ma_s).mean()
        result["ma10"] = result["close"].rolling(ma_m).mean()
        result["ma20"] = result["close"].rolling(ma_l).mean()
        result["ma60"] = result["close"].rolling(ma_t).mean()

        # 20日均线斜率（用于大盘趋势判断）
        result["ma20_slope"] = result["ma20"].diff()

        # ── 均线多头排列检查（规则4）──
        result["ma_aligned"] = (
            (result["ma5"] > result["ma10"]) &
            (result["ma10"] > result["ma20"]) &
            (result["ma20"] > result["ma60"])
        ).astype(int)

        # 60日均线不破检查
        result["above_ma60"] = (result["close"] > result["ma60"]).astype(int)
        # 20日内收盘价未跌破60日均线
        result["ma60_safe"] = result["above_ma60"].rolling(20).min().fillna(0).astype(int)

        # ── 强势识别（规则3）──
        # 每日涨幅
        result["daily_return"] = result["close"].pct_change()
        # 涨停标记
        result["is_limit_up"] = (result["daily_return"] >= limit_up_threshold).astype(int)
        # N日内涨停次数
        result["limit_up_count"] = result["is_limit_up"].rolling(strong_lookback).sum()

        # 突破型：N日最高价
        result["high_n"] = result["high"].rolling(breakout_high_period).max()
        # 今日是否创N日新高
        result["is_new_high"] = (result["high"] > result["high_n"].shift(1)).astype(int)
        # 突破日：涨幅达标 + 创新高
        result["is_breakout"] = (
            (result["daily_return"] > breakout_gain) &
            (result["is_new_high"] == 1)
        ).astype(int)
        # 成交量均值
        result["vol_ma20"] = result["volume"].rolling(20).mean()

        # ── 阶段识别 ──
        # 主升浪标记：涨停或突破成交量放大
        result["is_rally"] = (
            (result["is_limit_up"] == 1) |
            ((result["is_breakout"] == 1) & (result["volume"] > result["vol_ma20"] * breakout_vol_ratio))
        ).astype(int)

        # 滚动窗口内是否有主升浪
        result["had_rally"] = result["is_rally"].rolling(max_pb_days + strong_lookback).max().fillna(0).astype(int)

        # ── 回调检测（规则5-7）──
        # 近期最高价
        result["recent_high"] = result["high"].rolling(strong_lookback + max_pb_days).max()
        # 从最高点回撤幅度
        result["drawdown_pct"] = (result["recent_high"] - result["close"]) / result["recent_high"]
        # 回撤中的最低价
        result["recent_low"] = result["low"].rolling(max_pb_days).min()

        # 主升浪成交量峰值
        result["rally_max_vol"] = result["volume"].rolling(strong_lookback + max_pb_days).max()
        # 缩量检查：当前量 < 主升浪最大量 * 缩量比
        result["volume_contracted"] = (result["volume"] < result["rally_max_vol"] * vol_contract).astype(int)

        # 阴线实体幅度
        result["bearish_body"] = 0.0
        mask = result["close"] < result["open"]
        result.loc[mask, "bearish_body"] = (
            (result.loc[mask, "open"] - result.loc[mask, "close"]) / result.loc[mask, "open"]
        )

        # ── 买入信号（规则8）──
        # 条件：均线多头 + 曾有主升浪 + 正在回调 + 缩量 + 价格接近支撑
        result["near_ma20"] = (
            abs(result["close"] - result["ma20"]) / result["ma20"] < 0.02
        ).astype(int)

        # 斐波那契支撑位
        rally_range = result["recent_high"] - result["recent_low"].shift(1)
        rally_range = rally_range.replace(0, np.nan)
        result["fib_382"] = result["recent_high"] - rally_range * fib_strong
        result["fib_500"] = result["recent_high"] - rally_range * fib_normal
        result["near_fib"] = (
            (abs(result["close"] - result["fib_382"]) / result["close"] < 0.015) |
            (abs(result["close"] - result["fib_500"]) / result["close"] < 0.015)
        ).astype(int)

        # 核心买入条件
        result["buy_condition"] = (
            (result["had_rally"] == 1) &
            (result["ma_aligned"] == 1) &
            (result["ma60_safe"] == 1) &
            (result["drawdown_pct"] > 0.01) &
            (result["drawdown_pct"] < fib_normal + 0.05) &
            (result["volume_contracted"] == 1) &
            ((result["near_ma20"] == 1) | (result["near_fib"] == 1))
        )

        # 避免重复买入：近期已有买入信号后不再触发
        result["recent_buy"] = result["buy_condition"].rolling(min_pb_days).max().shift(1).fillna(0)
        result["buy_signal"] = (
            result["buy_condition"] &
            (result["recent_buy"] == 0)
        )

        # ── 卖出信号（规则9-12）──
        # 追踪持仓状态和入场价（通过前向填充模拟）
        result["in_position"] = 0
        result["entry_price"] = np.nan
        result["entry_idx"] = np.nan
        result["highest_since_entry"] = np.nan

        entry_price_val = np.nan
        entry_idx_val = np.nan
        highest_val = np.nan
        in_pos = 0
        days_in_pos = 0

        for i in range(n):
            if result["buy_signal"].iloc[i] and in_pos == 0:
                in_pos = 1
                entry_price_val = result["close"].iloc[i]
                entry_idx_val = i
                highest_val = result["close"].iloc[i]
                days_in_pos = 0
            elif in_pos == 1:
                days_in_pos += 1
                highest_val = max(highest_val, result["high"].iloc[i])

            result.loc[result.index[i], "in_position"] = in_pos
            if in_pos == 1:
                result.loc[result.index[i], "entry_price"] = entry_price_val
                result.loc[result.index[i], "entry_idx"] = entry_idx_val
                result.loc[result.index[i], "highest_since_entry"] = highest_val

        result["profit_pct"] = 0.0
        mask_pos = result["in_position"] == 1
        result.loc[mask_pos, "profit_pct"] = (
            (result.loc[mask_pos, "close"] - result.loc[mask_pos, "entry_price"])
            / result.loc[mask_pos, "entry_price"]
        )

        # 规则9：硬性止损
        result["stop_loss_hit"] = (
            (result["in_position"] == 1) &
            (result["close"] < result["entry_price"] * (1 - stop_loss))
        )

        # 技术止损：收盘价跌破20日均线超过2%
        result["ma_stop_hit"] = (
            (result["in_position"] == 1) &
            (result["close"] < result["ma20"] * (1 - ma_stop_buf))
        )

        # 规则10：时间止损
        result["days_in_trade"] = 0
        for i in range(n):
            if result["in_position"].iloc[i] == 1 and i > 0:
                prev_days = result["days_in_trade"].iloc[i - 1]
                result.loc[result.index[i], "days_in_trade"] = prev_days + 1 if prev_days > 0 else 1

        time_stop_d1 = int(params.get("time_stop_days_1", 5))
        time_stop_d2 = int(params.get("time_stop_days_2", 8))
        time_profit_1 = float(params.get("time_stop_profit_1", 3.0)) / 100.0

        result["time_stop_1"] = (
            (result["in_position"] == 1) &
            (result["days_in_trade"] >= time_stop_d1) &
            (result["profit_pct"] < time_profit_1)
        )
        result["time_stop_2"] = (
            (result["in_position"] == 1) &
            (result["days_in_trade"] >= time_stop_d2) &
            (result["close"] < result["highest_since_entry"])
        )

        # 规则11：移动止盈
        result["trail_stop_cost"] = (
            (result["in_position"] == 1) &
            (result["highest_since_entry"] > result["entry_price"] * (1 + trail_1)) &
            (result["close"] < result["entry_price"])
        )
        result["trail_stop_ma5"] = (
            (result["in_position"] == 1) &
            (result["highest_since_entry"] > result["entry_price"] * (1 + trail_2)) &
            (result["close"] < result["ma5"])
        )

        # 规则12：见顶信号
        result["vol_20d_high"] = result["volume"].rolling(20).max()
        result["top_stall"] = (
            (result["in_position"] == 1) &
            (result["volume"] >= result["vol_20d_high"]) &
            (result["daily_return"] < 0.02) &  # 放量滞涨
            (result["daily_return"] > -0.02)
        )
        result["top_big_drop"] = (
            (result["in_position"] == 1) &
            (result["daily_return"] < -0.05) &   # 长阴
            (result["volume"] > result["volume"].shift(1))  # 放量
        )
        deviation = float(params.get("top_deviation_pct", 30.0)) / 100.0
        result["top_deviation"] = (
            (result["in_position"] == 1) &
            ((result["close"] - result["ma20"]) / result["ma20"] > deviation)
        )

        # ── 综合卖出信号 ──
        result["sell_signal"] = (
            result["stop_loss_hit"] |
            result["ma_stop_hit"] |
            result["time_stop_1"] |
            result["time_stop_2"] |
            result["trail_stop_cost"] |
            result["trail_stop_ma5"] |
            result["top_stall"] |
            result["top_big_drop"] |
            result["top_deviation"]
        )

        # ── 信号强度 ──
        result["signal_strength"] = 0.0
        # 买入信号强度：基于均线排列强度 + 缩量程度 + 支撑接近度
        buy_strength = (
            result["buy_signal"].astype(float) *
            (0.4 + 0.3 * result["drawdown_pct"].fillna(0) / fib_normal +
             0.3 * (1 - result["volume"].fillna(0) / result["rally_max_vol"].replace(0, np.nan).fillna(1e9)))
        )
        buy_strength = buy_strength.clip(0, 1.0)
        result.loc[result["buy_signal"], "signal_strength"] = buy_strength[result["buy_signal"]]

        # 卖出信号强度：基于止损紧急程度
        result.loc[result["stop_loss_hit"], "signal_strength"] = -1.0
        result.loc[result["ma_stop_hit"], "signal_strength"] = -0.9
        result.loc[result["top_big_drop"], "signal_strength"] = -1.0
        result.loc[result["top_stall"], "signal_strength"] = -0.7
        result.loc[result["trail_stop_ma5"], "signal_strength"] = -0.6
        result.loc[result["trail_stop_cost"], "signal_strength"] = -0.5
        result.loc[result["time_stop_1"], "signal_strength"] = -0.4
        result.loc[result["time_stop_2"], "signal_strength"] = -0.5
        result.loc[result["top_deviation"], "signal_strength"] = -0.6

        # 清理临时列（保留调试列以便回测分析）
        debug_cols = [
            "ma5", "ma10", "ma20", "ma60", "ma20_slope",
            "ma_aligned", "above_ma60", "ma60_safe",
            "daily_return", "is_limit_up", "limit_up_count",
            "is_breakout", "is_rally", "had_rally",
            "recent_high", "drawdown_pct", "recent_low",
            "volume_contracted", "bearish_body",
            "near_ma20", "fib_382", "fib_500", "near_fib",
            "buy_condition", "recent_buy",
            "in_position", "entry_price", "entry_idx",
            "highest_since_entry", "profit_pct", "days_in_trade",
            "stop_loss_hit", "ma_stop_hit",
            "time_stop_1", "time_stop_2",
            "trail_stop_cost", "trail_stop_ma5",
            "top_stall", "top_big_drop", "top_deviation",
        ]
        # 只保留最终信号列 + 少量关键列
        keep_cols = [c for c in result.columns if c not in debug_cols or c in [
            "ma5", "ma10", "ma20", "ma60",
            "ma_aligned", "drawdown_pct", "volume_contracted",
            "buy_condition", "in_position", "profit_pct",
        ]]
        # 实际上回测需要更多列，全部保留
        return result

    # ═══════════════════════════════════════════════════════════════
    # 趋势跟踪策略（ADX + 均线 + ATR）
    # ═══════════════════════════════════════════════════════════════
    def _trend_following_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Trend Following Strategy — ADX确认趋势 + 均线多头 + ATR动态止损.

        核心逻辑：
          1. 均线多头排列：MA5 > MA20 > MA60
          2. ADX确认趋势强度 > 阈值
          3. 买入：趋势确认 + 价格回调至MA20附近 + 成交量确认
          4. 卖出：ATR移动止损 / 均线死叉 / 趋势衰竭
        """
        result = df.copy()
        n = len(result)
        if n < 60:
            result["buy_signal"] = False
            result["sell_signal"] = False
            result["signal_strength"] = 0.0
            return result

        ma_s = int(params.get("ma_short", 5))
        ma_m = int(params.get("ma_medium", 20))
        ma_l = int(params.get("ma_long", 60))
        adx_period = int(params.get("adx_period", 14))
        adx_threshold = int(params.get("adx_threshold", 25))
        atr_period = int(params.get("atr_period", 14))
        atr_mult = float(params.get("atr_multiplier", 2.0))
        trailing_stop = float(params.get("trailing_stop_pct", 8.0)) / 100.0
        vol_confirm = float(params.get("volume_confirm_ratio", 1.2))

        # ── 均线 ──
        result["ma5"] = result["close"].rolling(ma_s).mean()
        result["ma20"] = result["close"].rolling(ma_m).mean()
        result["ma60"] = result["close"].rolling(ma_l).mean()

        # 均线多头
        result["ma_bullish"] = (
            (result["ma5"] > result["ma20"]) &
            (result["ma20"] > result["ma60"])
        ).astype(int)

        # ── ADX ──
        result["tr"] = np.maximum(
            result["high"] - result["low"],
            np.maximum(
                abs(result["high"] - result["close"].shift(1)),
                abs(result["low"] - result["close"].shift(1)),
            )
        )
        result["atr"] = result["tr"].rolling(atr_period).mean()
        result["up_move"] = result["high"] - result["high"].shift(1)
        result["down_move"] = result["low"].shift(1) - result["low"]
        result["plus_dm"] = np.where(
            (result["up_move"] > result["down_move"]) & (result["up_move"] > 0),
            result["up_move"], 0
        )
        result["minus_dm"] = np.where(
            (result["down_move"] > result["up_move"]) & (result["down_move"] > 0),
            result["down_move"], 0
        )
        result["plus_di"] = 100 * (result["plus_dm"].ewm(alpha=1 / adx_period, adjust=False).mean() / result["atr"])
        result["minus_di"] = 100 * (result["minus_dm"].ewm(alpha=1 / adx_period, adjust=False).mean() / result["atr"])
        result["dx"] = 100 * abs(result["plus_di"] - result["minus_di"]) / (result["plus_di"] + result["minus_di"] + 1e-9)
        result["adx"] = result["dx"].ewm(alpha=1 / adx_period, adjust=False).mean()

        # 成交量均线
        result["vol_ma20"] = result["volume"].rolling(20).mean()

        # ── 买入信号：趋势确认 + 回调至MA20 + 放量 ──
        result["trend_ready"] = (
            (result["ma_bullish"] == 1) &
            (result["adx"] > adx_threshold) &
            (result["plus_di"] > result["minus_di"])
        ).astype(int)

        # 价格在MA20附近（回调买入）
        result["near_ma20"] = (
            abs(result["close"] - result["ma20"]) / result["ma20"] < 0.03
        ).astype(int)

        result["buy_signal"] = (
            (result["trend_ready"] == 1) &
            (result["near_ma20"] == 1) &
            (result["volume"] > result["vol_ma20"] * vol_confirm) &
            (result["close"] > result["close"].shift(1))  # 当日收阳
        )

        # ── 卖出信号 ──
        # 均线死叉
        result["ma_dead_cross"] = (
            (result["ma5"] < result["ma20"]) &
            (result["ma5"].shift(1) >= result["ma20"].shift(1))
        )
        # ADX趋势衰竭
        result["adx_fading"] = (
            (result["adx"] < adx_threshold - 5) |
            (result["adx"] < result["adx"].shift(3))
        )
        # 价格跌破MA60
        result["below_ma60"] = result["close"] < result["ma60"]

        result["sell_signal"] = (
            result["ma_dead_cross"] |
            (result["below_ma60"] & result["adx_fading"])
        )

        # ── 信号强度 ──
        result["signal_strength"] = 0.0
        result.loc[result["buy_signal"], "signal_strength"] = (
            (result.loc[result["buy_signal"], "adx"] - adx_threshold) / 50
        ).clip(0, 1.0)
        result.loc[result["sell_signal"], "signal_strength"] = -0.8

        return result

    # ═══════════════════════════════════════════════════════════════
    # 右侧入场策略（Core 3）— 回踩20日线 + 缩量止跌 + 放量阳线突破
    # ═══════════════════════════════════════════════════════════════
    def _right_side_entry_strategy(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Right-Side Entry Strategy — 纯右侧趋势确认入场.

        买入条件（全部满足）：
          1. 回踩20日均线（价格在20MA ± 2%以内）
          2. 缩量止跌（近期成交量收缩至均值50%以下）
          3. 放量阳线突破（当日收阳 + 成交量 > 前日 * 1.5）
          4. 20日均线走平或向上
          5. 价格站稳60日均线（长期趋势完好）
          6. 前期有缩量过程

        卖出条件（任一触发）：
          1. 有效跌破20日均线（收盘 < 20MA * 0.98）
          2. 跌破60日均线（趋势终结）
          3. 放量大跌（单日跌 > 7% + 放量）
        """
        result = df.copy()
        n = len(result)
        if n < 60:
            result["buy_signal"] = False
            result["sell_signal"] = False
            result["signal_strength"] = 0.0
            return result

        # ── 参数提取 ──
        ma_short = int(params.get("ma_short", 5))
        ma_medium = int(params.get("ma_medium", 20))
        ma_long = int(params.get("ma_long", 60))
        near_ma_pct = float(params.get("pullback_near_ma_pct", 2.0)) / 100.0
        vol_contract_ratio = float(params.get("vol_contraction_ratio", 0.5))
        vol_expand_ratio = float(params.get("vol_expansion_ratio", 1.5))
        stop_loss_ma_break = float(params.get("stop_loss_ma_break_pct", 2.0)) / 100.0
        hard_stop = float(params.get("hard_stop_pct", 7.0)) / 100.0

        # ── 计算均线 ──
        result["ma5"] = result["close"].rolling(ma_short).mean()
        result["ma20"] = result["close"].rolling(ma_medium).mean()
        result["ma60"] = result["close"].rolling(ma_long).mean()
        result["ma20_slope"] = result["ma20"].diff()

        # ── 成交量指标 ──
        result["vol_ma20"] = result["volume"].rolling(20).mean()
        result["vol_ratio"] = result["volume"] / result["vol_ma20"].replace(0, np.nan)
        result["daily_return"] = result["close"].pct_change()

        # ── 每日K线形态 ──
        result["is_bullish"] = (result["close"] > result["open"]).astype(int)
        result["is_bearish"] = (result["close"] < result["open"]).astype(int)

        # ── 阶段高点和回撤 ──
        result["high_20d"] = result["high"].rolling(20).max()
        result["drawdown_from_high"] = (result["high_20d"] - result["close"]) / result["high_20d"]

        # ── 买入条件 ──

        # 条件1：回踩20日均线
        result["near_ma20"] = (
            abs(result["close"] - result["ma20"]) / result["ma20"].replace(0, np.nan) < near_ma_pct
        ).astype(int)

        # 条件2：缩量止跌（近期量缩至均值以下）
        result["vol_contracted"] = (result["vol_ratio"] < vol_contract_ratio).astype(int)
        # 近5日有过缩量
        result["had_vol_shrink"] = result["vol_contracted"].rolling(5).max().fillna(0).astype(int)

        # 条件3：放量阳线突破
        result["vol_expanding"] = (
            result["volume"] > result["volume"].shift(1) * vol_expand_ratio
        ).astype(int)
        result["breakout_candle"] = (
            (result["is_bullish"] == 1) &
            (result["vol_expanding"] == 1)
        ).astype(int)

        # 条件4：20日均线走平或向上
        result["ma20_rising"] = (result["ma20_slope"] >= 0).astype(int)

        # 条件5：站稳60日均线
        result["above_ma60"] = (result["close"] > result["ma60"]).astype(int)

        # 条件6：不是追高（回撤幅度合理，不在高点附近）
        result["not_chasing"] = (result["drawdown_from_high"] > 0.01).astype(int)

        # ── 综合买入信号 ──
        # 6个条件中至少满足5个
        buy_condition_score = (
            result["near_ma20"] +
            result["had_vol_shrink"] +
            result["breakout_candle"] +
            result["ma20_rising"] +
            result["above_ma60"] +
            result["not_chasing"]
        )
        result["buy_condition_score"] = buy_condition_score
        result["buy_signal"] = buy_condition_score >= 5

        # 避免连续买入：前5天有买入则不触发
        result["recent_buy"] = result["buy_signal"].rolling(5).max().shift(1).fillna(0)
        result["buy_signal"] = result["buy_signal"] & (result["recent_buy"] == 0)

        # ── 卖出条件 ──

        # 条件1：有效跌破20日均线
        result["break_ma20"] = (
            result["close"] < result["ma20"] * (1 - stop_loss_ma_break)
        ).astype(int)

        # 条件2：跌破60日均线（趋势终结）
        result["break_ma60"] = (result["close"] < result["ma60"]).astype(int)

        # 条件3：放量大跌
        result["crash_day"] = (
            (result["daily_return"] < -hard_stop) &
            (result["vol_ratio"] > 1.5)
        ).astype(int)

        result["sell_signal"] = (
            (result["break_ma20"] == 1) |
            (result["break_ma60"] == 1) |
            (result["crash_day"] == 1)
        )

        # ── 信号强度 ──
        result["signal_strength"] = 0.0

        # 买入信号强度：基于条件满足程度
        result.loc[result["buy_signal"], "signal_strength"] = (
            result.loc[result["buy_signal"], "buy_condition_score"] / 6.0
        ).clip(0, 1.0)

        # 卖出信号强度
        result.loc[result["break_ma20"] == 1, "signal_strength"] = -0.8
        result.loc[result["break_ma60"] == 1, "signal_strength"] = -0.9
        result.loc[result["crash_day"] == 1, "signal_strength"] = -1.0

        return result


strategy_engine = StrategyEngine()
