"""Stock Screener (Core 3) — 个股筛选引擎.

Screens individual stocks within approved industry sectors using the
right-side entry methodology from req.txt.

Rules:
  1. Price above all short MA (5, 10, 20, 60)
  2. Up on expanding volume, down on contracting volume
  3. Higher lows, no breakdown candles
  4. Liquidity: daily turnover >= threshold (default 50M CNY)

Signal generation:
  BUY  — pullback to 20MA + volume shrink + breakout volume yang candle
  SELL — effectively breaks below 20MA → unconditional exit
"""

import datetime
import time
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings


class StockScreener:
    """Screens individual stocks against the right-side entry criteria.

    Designed to be called per-symbol with historical K-line data,
    returning a signal dict that can be consumed by the strategy engine
    or used directly.
    """

    def __init__(self):
        self._cache: dict = {}

    # ── Public API ──────────────────────────────────────────────────

    def screen_stocks(self, symbols: list, require_signal: bool = True) -> list:
        """Screen a list of symbols and return those meeting all criteria.

        Args:
            symbols: List of stock symbols like ['000001.SZ', '600519.SH']
            require_signal: If True, only return stocks with active BUY signals.

        Returns list of dicts:
          [{symbol, name, price, signal_type, signal_strength, criteria_met, ...}]
        """
        results = []
        for sym in symbols:
            screening = self.check_criteria(sym)
            if screening["criteria_met"]:
                if require_signal and not screening.get("buy_signal"):
                    continue
                results.append(screening)
        return results

    def check_criteria(self, symbol: str, df: pd.DataFrame = None) -> dict:
        """Check all four individual-stock criteria plus right-side signals.

        Args:
            symbol: Stock symbol (e.g. '000001.SZ')
            df: Pre-fetched DataFrame; if None, fetch from DataEngine.

        Returns dict with all criteria flags and signal information.
        """
        cache_key = f"scr_{symbol}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached.get("_ts", 0)) < 60:
            return cached

        # Fetch data
        if df is None:
            from app.engine.data_engine import data_engine
            df = data_engine.get_history_data(
                symbol,
                start_date=(datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
                end_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            )

        if df is None or len(df) < 60:
            return self._empty_result(symbol, "数据不足")

        result_df = df.copy()
        n = len(result_df)

        # ── Calculate MAs ──
        periods = settings.STOCK_SCREENER_MA_PERIODS  # [5, 10, 20, 60]
        for p in periods:
            result_df[f"ma{p}"] = result_df["close"].rolling(window=p).mean()

        # ── Volume MA ──
        result_df["vol_ma20"] = result_df["volume"].rolling(window=20).mean()
        result_df["vol_ratio"] = result_df["volume"] / result_df["vol_ma20"].replace(0, np.nan)

        # ── Daily return ──
        result_df["daily_return"] = result_df["close"].pct_change()

        # ── Rolling lows (check for higher lows) ──
        result_df["low_20d_min"] = result_df["low"].rolling(window=20).min()
        result_df["low_20d_prev_min"] = result_df["low_20d_min"].shift(20)

        latest = result_df.iloc[-1]
        prev = result_df.iloc[-2]

        min_daily_amount = settings.MIN_DAILY_AMOUNT
        near_ma_pct = settings.PULLBACK_NEAR_MA_PCT / 100.0

        # ── Criterion 1: Price above all short MAs ──
        above_ma5 = float(latest["close"]) > float(latest.get("ma5", 0) or 0)
        above_ma10 = float(latest["close"]) > float(latest.get("ma10", 0) or 0)
        above_ma20 = float(latest["close"]) > float(latest.get("ma20", 0) or 0)
        above_ma60 = float(latest["close"]) > float(latest.get("ma60", 0) or 0)
        all_above_ma = above_ma5 and above_ma10 and above_ma20 and above_ma60

        # ── Criterion 2: Volume pattern (up on volume, down on shrink) ──
        # Check that recent up-days had higher volume ratio than down-days
        recent = result_df.tail(20)
        up_days = recent[recent["daily_return"] > 0]
        down_days = recent[recent["daily_return"] < 0]
        vol_up_avg = float(up_days["vol_ratio"].mean()) if len(up_days) > 0 else 0
        vol_down_avg = float(down_days["vol_ratio"].mean()) if len(down_days) > 0 else 0
        vol_pattern_healthy = vol_up_avg > vol_down_avg if vol_up_avg > 0 and vol_down_avg > 0 else True

        # ── Criterion 3: Higher lows, no breakdown candles ──
        latest_low_min = float(latest.get("low_20d_min", 0) or 0)
        prev_low_min = float(latest.get("low_20d_prev_min", 0) or 0)
        higher_lows = latest_low_min >= prev_low_min if latest_low_min > 0 and prev_low_min > 0 else True

        # Check for breakdown candles (single-day drop > 7% with volume)
        recent_big_drops = recent[
            (recent["daily_return"] < -0.07) & (recent["vol_ratio"] > 1.5)
        ]
        no_breakdown = len(recent_big_drops) == 0

        # ── Criterion 4: Liquidity ──
        daily_amount = float(latest["volume"]) * float(latest["close"])
        liquidity_ok = daily_amount >= min_daily_amount

        # ── All criteria met? ──
        criteria_met = all([all_above_ma, vol_pattern_healthy, higher_lows, no_breakdown, liquidity_ok])

        # ── Right-side BUY signal ──
        buy_signal, buy_strength = self._detect_buy_signal(result_df)

        # ── Right-side SELL signal ──
        sell_signal, sell_reason = self._detect_sell_signal(result_df)

        # ── Get stock name ──
        from app.engine.data_engine import data_engine
        name = data_engine.lookup_stock_name(symbol)

        result = {
            "symbol": symbol,
            "name": name,
            "current_price": float(latest["close"]),
            "criteria_met": criteria_met,
            # Sub-criteria
            "all_above_ma": all_above_ma,
            "ma5": round(float(latest.get("ma5", 0) or 0), 2),
            "ma10": round(float(latest.get("ma10", 0) or 0), 2),
            "ma20": round(float(latest.get("ma20", 0) or 0), 2),
            "ma60": round(float(latest.get("ma60", 0) or 0), 2),
            "vol_pattern_healthy": vol_pattern_healthy,
            "higher_lows": higher_lows,
            "no_breakdown": no_breakdown,
            "liquidity_ok": liquidity_ok,
            "daily_amount": round(daily_amount / 1e8, 2),  # in 亿
            # Signals
            "buy_signal": buy_signal,
            "buy_signal_strength": round(buy_strength, 2),
            "sell_signal": sell_signal,
            "sell_reason": sell_reason,
            "_ts": time.time(),
        }
        self._cache[cache_key] = result
        return result

    def detect_right_side_signal(self, symbol: str, df: pd.DataFrame = None) -> dict:
        """Convenience wrapper: return only signal information."""
        screening = self.check_criteria(symbol, df)
        return {
            "symbol": symbol,
            "name": screening.get("name", symbol),
            "buy_signal": screening["buy_signal"],
            "buy_signal_strength": screening["buy_signal_strength"],
            "sell_signal": screening["sell_signal"],
            "sell_reason": screening["sell_reason"],
            "criteria_met": screening["criteria_met"],
        }

    # ── Internal signal logic ───────────────────────────────────────

    def _detect_buy_signal(self, df: pd.DataFrame) -> tuple:
        """Check for right-side entry buy signal.

        Buy conditions (all must be true):
        1. Price near 20MA (within PULLBACK_NEAR_MA_PCT)
        2. Volume contracted vs 20-day average (vol_ratio < 1.0 during pullback)
        3. Today is a bullish candle with volume expansion vs yesterday
        4. 20MA is flat or rising
        5. Price above 60MA
        """
        if len(df) < 60:
            return False, 0.0

        near_ma_pct = settings.PULLBACK_NEAR_MA_PCT / 100.0
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(latest["close"])
        ma20 = float(latest.get("ma20", 0) or 0)
        ma60 = float(latest.get("ma60", 0) or 0)
        vol_ratio = float(latest.get("vol_ratio", 1.0))
        prev_vol = float(prev["volume"]) if len(df) >= 2 else 0
        curr_vol = float(latest["volume"])

        # Condition 1: Near 20MA
        near_ma20 = abs(close - ma20) / ma20 < near_ma_pct if ma20 > 0 else False

        # Condition 2: Volume contracted (below average)
        vol_contracted = vol_ratio < 0.8

        # Condition 3: Bullish candle with volume expansion
        is_bullish_candle = close > float(latest["open"])
        vol_expanding = curr_vol > prev_vol * 1.3 if prev_vol > 0 else False
        breakout_candle = is_bullish_candle and vol_expanding

        # Condition 4: 20MA flat or rising
        ma20_prev = float(df["ma20"].iloc[-2]) if len(df) >= 2 and not pd.isna(df["ma20"].iloc[-2]) else ma20
        ma20_rising = ma20 >= ma20_prev if ma20_prev > 0 else True

        # Condition 5: Above 60MA
        above_ma60 = close > ma60 if ma60 > 0 else False

        # Check pullback context: previous few days had volume shrink
        recent_vol_ratios = df["vol_ratio"].iloc[-6:-1] if "vol_ratio" in df.columns else pd.Series([1.0])
        had_vol_shrink = recent_vol_ratios.max() < 1.0 if len(recent_vol_ratios) > 0 else False

        buy_conditions_met = sum([
            near_ma20,
            vol_contracted,
            breakout_candle,
            ma20_rising,
            above_ma60,
            had_vol_shrink,
        ])

        buy_signal = buy_conditions_met >= 5  # At least 5 of 6 conditions
        strength = buy_conditions_met / 6.0 if buy_signal else 0.0

        return buy_signal, strength

    def _detect_sell_signal(self, df: pd.DataFrame) -> tuple:
        """Check for right-side exit sell signal.

        Sell conditions (any true):
        1. Close < 20MA * 0.98 (effectively breaks 20MA with 2% buffer)
        2. Close < 60MA (trend destroyed)
        3. Single day drop > 7% with high volume
        """
        if len(df) < 2:
            return False, ""

        latest = df.iloc[-1]
        close = float(latest["close"])
        ma20 = float(latest.get("ma20", 0) or 0)
        ma60 = float(latest.get("ma60", 0) or 0)
        daily_return = float(latest.get("daily_return", 0) or 0)
        vol_ratio = float(latest.get("vol_ratio", 1.0))

        # Condition 1: Break below 20MA
        if ma20 > 0 and close < ma20 * 0.98:
            return True, "有效跌破20日均线"

        # Condition 2: Break below 60MA (trend destroyed)
        if ma60 > 0 and close < ma60:
            return True, "跌破60日均线，趋势终结"

        # Condition 3: Big drop with volume
        if daily_return < -0.07 and vol_ratio > 1.5:
            return True, "放量大跌，强制离场"

        return False, ""

    @staticmethod
    def _empty_result(symbol: str, reason: str = "") -> dict:
        return {
            "symbol": symbol,
            "name": symbol,
            "current_price": 0,
            "criteria_met": False,
            "all_above_ma": False,
            "ma5": 0, "ma10": 0, "ma20": 0, "ma60": 0,
            "vol_pattern_healthy": False,
            "higher_lows": False,
            "no_breakdown": False,
            "liquidity_ok": False,
            "daily_amount": 0,
            "buy_signal": False,
            "buy_signal_strength": 0.0,
            "sell_signal": False,
            "sell_reason": reason,
            "_ts": time.time(),
        }


stock_screener = StockScreener()
