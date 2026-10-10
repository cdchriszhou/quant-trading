"""Short-horizon market forecast for A-share short-hold recommendations.

Adapted from installed agent skills (mphinance / VernonOY):
  - uptrend-analyzer: 0-100 breadth/health score → exposure bands
  - market-top-detector: distribution-day / leadership deterioration risk
  - market-breadth-analyzer: participation health
  - market-environment-analysis: risk-on/off + 1-5d outlook
  - alpha-signal: regime-aware position sizing for target portfolio

This engine is **forward-looking** (5–10 trading days), not a binary can_trade gate.
It never blocks recommendations alone; it scales risk (score / exposure / bias).
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pandas as pd


class MarketForecastEngine:
    """0–100 short-horizon market outlook + exposure multiplier."""

    def __init__(self):
        self._cache: dict = {}
        self._cache_ts: float = 0.0
        self._ttl: float = 60.0

    def forecast(self, horizon_days: int = 7) -> dict:
        now = time.time()
        if self._cache and (now - self._cache_ts) < self._ttl:
            out = dict(self._cache)
            out["horizon_days"] = horizon_days
            return out

        from app.engine.market_env_engine import market_env_engine

        df = market_env_engine.get_avg_price_kline(160)
        env = market_env_engine.check_environment()
        market_perf = env.get("market_performance") or {}

        result = self._score_frame(
            df,
            breadth_bias=market_perf.get("breadth_bias") or "unknown",
            index_bias=market_perf.get("index_bias") or "unknown",
            breadth_summary=market_perf.get("breadth_summary") or "",
            index_summary=market_perf.get("index_summary") or "",
            horizon_days=horizon_days,
        )
        # Blend live env checklist into narrative
        result["env_state"] = env.get("env_state")
        result["env_can_trade"] = bool(env.get("can_trade"))
        result["skills_basis"] = [
            "uptrend-analyzer",
            "market-top-detector",
            "market-breadth-analyzer",
            "market-environment-analysis",
            "alpha-signal",
        ]
        self._cache = result
        self._cache_ts = now
        return result

    def forecast_series(self, start_date: str, end_date: str, lookback: int = 400) -> pd.DataFrame:
        """Historical daily forecast for backtests (no look-ahead).

        Each row uses only data available on that close (signals as-of t).
        """
        from app.engine.market_env_engine import market_env_engine

        df = market_env_engine.get_avg_price_kline(lookback)
        if df is None or len(df) < 60:
            return pd.DataFrame()

        df = df.copy()
        df["date"] = df["date"].astype(str).str[:10]
        rows = []
        # Walk forward with expanding window ending at i
        closes = pd.to_numeric(df["close"], errors="coerce")
        volumes = pd.to_numeric(df["volume"], errors="coerce")
        for i in range(60, len(df)):
            d = df["date"].iloc[i]
            if d < start_date or d > end_date:
                continue
            window = pd.DataFrame(
                {
                    "date": df["date"].iloc[: i + 1].values,
                    "close": closes.iloc[: i + 1].values,
                    "volume": volumes.iloc[: i + 1].values,
                    "open": pd.to_numeric(df.get("open", closes), errors="coerce").iloc[: i + 1].values
                    if "open" in df.columns
                    else closes.iloc[: i + 1].values,
                    "high": pd.to_numeric(df.get("high", closes), errors="coerce").iloc[: i + 1].values
                    if "high" in df.columns
                    else closes.iloc[: i + 1].values,
                    "low": pd.to_numeric(df.get("low", closes), errors="coerce").iloc[: i + 1].values
                    if "low" in df.columns
                    else closes.iloc[: i + 1].values,
                }
            )
            scored = self._score_frame(window, breadth_bias="unknown", index_bias="unknown")
            rows.append(
                {
                    "date": d,
                    "forecast_score": scored["forecast_score"],
                    "horizon_bias": scored["horizon_bias"],
                    "exposure_mult": scored["exposure_mult"],
                    "top_risk": scored["top_risk"],
                    "permit_new": scored["permit_new"],
                }
            )
        return pd.DataFrame(rows)

    def _score_frame(
        self,
        df: Optional[pd.DataFrame],
        *,
        breadth_bias: str = "unknown",
        index_bias: str = "unknown",
        breadth_summary: str = "",
        index_summary: str = "",
        horizon_days: int = 7,
    ) -> dict:
        if df is None or len(df) < 40:
            return self._empty(horizon_days, "行情不足，短线展望中性偏谨慎")

        d = df.copy()
        for col in ("close", "volume"):
            d[col] = pd.to_numeric(d[col], errors="coerce")
        if "open" not in d.columns:
            d["open"] = d["close"]
        else:
            d["open"] = pd.to_numeric(d["open"], errors="coerce")
        d = d.dropna(subset=["close"])
        if len(d) < 40:
            return self._empty(horizon_days, "行情不足，短线展望中性偏谨慎")

        close = d["close"]
        vol = d["volume"].fillna(0)
        open_p = d["open"].fillna(close)

        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean() if len(d) >= 60 else ma20
        vol_ma20 = vol.rolling(20).mean()

        c = float(close.iloc[-1])
        o = float(open_p.iloc[-1])
        m5, m10, m20 = float(ma5.iloc[-1]), float(ma10.iloc[-1]), float(ma20.iloc[-1])
        m60 = float(ma60.iloc[-1]) if not pd.isna(ma60.iloc[-1]) else m20
        ma20_slope = float(ma20.iloc[-1] - ma20.iloc[-4]) if len(ma20) >= 4 else 0.0
        dist_ma20 = (c - m20) / m20 if m20 > 0 else 0.0
        vol_ratio = float(vol.iloc[-1] / vol_ma20.iloc[-1]) if float(vol_ma20.iloc[-1] or 0) > 0 else 1.0
        ret_5 = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0.0
        ret_10 = float(close.iloc[-1] / close.iloc[-11] - 1) if len(close) >= 11 else 0.0

        # ── Component 1: Trend structure (30) — uptrend-analyzer / env ──
        trend = 0.0
        if c > m20:
            trend += 10
        elif c > m20 * 0.975 and ma20_slope >= 0 and m5 >= m10 >= m20:
            # Shallow pullback under MA20: still constructive (skills: dip ≠ bear)
            trend += 7
        if c > m60:
            trend += 6
        elif c > m60 * 0.97:
            trend += 3
        if m5 >= m10 >= m20:
            trend += 10
        elif c > m20 and m5 > m20:
            trend += 5
        if ma20_slope >= 0:
            trend += 4
        trend = min(30.0, trend)

        # ── Component 2: Momentum (20) ──
        mom = 0.0
        if ret_5 > 0.02:
            mom += 10
        elif ret_5 > 0:
            mom += 6
        elif ret_5 > -0.02:
            mom += 3
        if ret_10 > 0.03:
            mom += 10
        elif ret_10 > 0:
            mom += 5
        elif ret_10 > -0.03:
            mom += 2
        mom = min(20.0, mom)

        # ── Component 3: Breadth / participation (20) ──
        breadth = 10.0  # unknown baseline
        if breadth_bias == "bull":
            breadth = 18.0
        elif breadth_bias == "bear":
            breadth = 4.0
        elif breadth_bias == "mixed":
            breadth = 10.0
        if index_bias == "bull":
            breadth = min(20.0, breadth + 2)
        elif index_bias == "bear":
            # Soften if structure is shallow pullback (MA stack + rising MA20)
            if c > m20 * 0.975 and ma20_slope >= 0 and m5 >= m10 >= m20:
                breadth = max(0.0, breadth - 2)
            else:
                breadth = max(0.0, breadth - 4)
        # Historical proxy when breadth unknown: 5d vs 20d strength
        if breadth_bias == "unknown":
            if ret_5 > 0 and ma20_slope >= 0:
                breadth = 14.0
            elif ret_5 < -0.02 or ma20_slope < 0:
                breadth = 6.0

        # ── Component 4: Inverse top-risk (20) — market-top-detector ──
        # Distribution days: down close with volume > prior day, last 25 sessions
        dist_days = 0
        look = min(25, len(d) - 1)
        for i in range(-look, 0):
            prev_v = float(vol.iloc[i - 1]) if abs(i - 1) < len(vol) else 0
            day_c = float(close.iloc[i])
            day_o = float(open_p.iloc[i])
            day_v = float(vol.iloc[i])
            if day_c < day_o and day_v > prev_v * 1.05 and day_c < float(close.iloc[i - 1]):
                dist_days += 1
        # Leadership proxy: sharp extension then stall
        stalled = dist_ma20 > 0.08 and ret_5 < 0.005
        top_raw = min(100.0, dist_days * 12.0 + (25.0 if stalled else 0.0))
        top_comp = max(0.0, 20.0 - top_raw * 0.20)  # high top risk → low contribution

        # ── Component 5: Volatility / extension hygiene (10) ──
        hyg = 10.0
        if dist_ma20 > 0.10:
            hyg -= 6
        elif dist_ma20 > 0.06:
            hyg -= 3
        if vol_ratio > 2.2 and c < o:
            hyg -= 4
        if vol_ratio < 0.5:
            hyg -= 2
        hyg = max(0.0, min(10.0, hyg))

        score = round(trend + mom + breadth + top_comp + hyg, 1)
        score = float(max(0.0, min(100.0, score)))

        # Zones from uptrend-analyzer exposure guidance
        if score >= 80:
            zone, exposure, bias = "strong_bull", 1.0, "bull"
        elif score >= 60:
            zone, exposure, bias = "bull", 0.9, "bull"
        elif score >= 40:
            zone, exposure, bias = "neutral", 0.7, "neutral"
        elif score >= 20:
            zone, exposure, bias = "cautious", 0.45, "bear"
        else:
            zone, exposure, bias = "bear", 0.25, "bear"

        # Overheat: cut exposure even if score mid-high (top-detector)
        if dist_ma20 > 0.10:
            exposure = min(exposure, 0.5)
            if bias == "bull":
                bias = "neutral"

        permit_new = score >= 35 and dist_days < 6
        top_risk = round(top_raw, 1)

        signals = []
        if m5 >= m10 >= m20 and c > m20:
            signals.append("均线多头，短线结构偏多")
        if breadth_bias == "bull":
            signals.append(f"板块广度偏强（{breadth_summary}）".rstrip("（）"))
        if dist_days >= 4:
            signals.append(f"近25日派发日约 {dist_days} 次，短线见顶风险上升")
        if ret_5 > 0.02 and ma20_slope >= 0:
            signals.append(f"5日动量 +{ret_5 * 100:.1f}%，趋势延续概率偏高")
        if dist_ma20 > 0.08:
            signals.append(f"偏离 MA20 {dist_ma20 * 100:.1f}%，追高风险")

        message = {
            "strong_bull": "短线展望偏强 — 可正常/加大精选仓位",
            "bull": "短线展望偏多 — 正常精选开仓",
            "neutral": "短线展望中性 — 缩小仓位、提高个股门槛",
            "cautious": "短线展望偏弱 — 防御精选，严控数量与仓位",
            "bear": "短线展望偏空 — 仅极少数高质量回踩标的",
        }.get(zone, "短线展望中性")

        return {
            "forecast_score": score,
            "zone": zone,
            "horizon_bias": bias,
            "horizon_days": horizon_days,
            "exposure_mult": exposure,
            "permit_new": permit_new,
            "top_risk": top_risk,
            "distribution_days_25": dist_days,
            "components": {
                "trend": round(trend, 1),
                "momentum": round(mom, 1),
                "breadth": round(breadth, 1),
                "anti_top": round(top_comp, 1),
                "hygiene": round(hyg, 1),
            },
            "ret_5": round(ret_5 * 100, 2),
            "ret_10": round(ret_10 * 100, 2),
            "dist_ma20_pct": round(dist_ma20 * 100, 2),
            "index_bias": index_bias,
            "breadth_bias": breadth_bias,
            "index_summary": index_summary,
            "breadth_summary": breadth_summary,
            "signals": signals[:6],
            "message": message,
        }

    @staticmethod
    def _empty(horizon_days: int, message: str) -> dict:
        return {
            "forecast_score": 45.0,
            "zone": "neutral",
            "horizon_bias": "neutral",
            "horizon_days": horizon_days,
            "exposure_mult": 0.7,
            "permit_new": True,
            "top_risk": 30.0,
            "distribution_days_25": 0,
            "components": {},
            "signals": [],
            "message": message,
        }


market_forecast_engine = MarketForecastEngine()
