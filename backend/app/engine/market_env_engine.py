"""Market Environment Engine (Core 1) — 大盘环境过滤.

基于真实平均股价（截面均值；可选配置交易所指数代码）判断开仓环境。
结合 A 股短线清单（趋势 / 回踩距离 / 量能 / 高低点），避免「仅站上 MA20
就允许开仓」的过热追高。

状态：
  bull     — 趋势健康且未过度伸展 → 允许开仓
  bear     — 空头结构或趋势破坏 → 锁定买入
  neutral  — 震荡 / 数据不足 / 多头过热 → 暂停新开仓
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings


class MarketEnvEngine:
    """Broad-market gate for new buys.

    When bearish or overheated, buy signals / capital-matched opens are locked.
    """

    def __init__(self):
        self._cache: dict = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 60.0

    # ── Public API ──────────────────────────────────────────────────

    def check_environment(self) -> dict:
        now = time.time()
        if self._cache and (now - self._cache_ts) < self._cache_ttl:
            return self._cache

        result = self._evaluate_environment()
        self._cache = result
        self._cache_ts = now
        return result

    def is_bullish(self) -> bool:
        return self.check_environment().get("can_trade", False)

    def is_bearish(self) -> bool:
        return self.check_environment().get("env_state") == "bear"

    def get_env_state(self) -> str:
        return self.check_environment().get("env_state", "neutral")

    def get_avg_price_kline(self, count: int = 120) -> pd.DataFrame:
<<<<<<< HEAD
        """Build a K-line DataFrame approximating the average stock price.

        Uses 上证指数 (000001.SH) K-line scaled to ~15 CNY (typical A-share price)
        as a fast proxy. This avoids fetching history for 60+ individual stocks
        which was the primary cause of homepage timeouts.

        For the purpose of market environment analysis (MA alignment, trend direction,
        volume health), the shape of the curve matters more than absolute price level.
        """
        from app.engine.data_engine import data_engine

        # Fast path: use 上证指数 K-line (1 HTTP request, cached)
        try:
            base_kline = data_engine.get_kline_data("000001.SH", "1d", count)
            if base_kline and len(base_kline) >= 20:
                # Scale from index level (~3000) to average stock price (~15)
                first_close = base_kline[0]["close"]
                scale = 15.0 / first_close if first_close > 100 else 1.0

                rows = []
                for k in base_kline:
                    rows.append({
                        "date": k["date"],
                        "open": round(k["open"] * scale, 2),
                        "close": round(k["close"] * scale, 2),
                        "high": round(k["high"] * scale, 2),
                        "low": round(k["low"] * scale, 2),
                        "volume": k.get("volume", 0),
                    })
                result = pd.DataFrame(rows)
                if len(result) >= 20:
                    return result
        except Exception as e:
            print(f"[MarketEnv] Fast kline failed: {e}")

        # Fallback: generate synthetic data
        return self._generate_fallback_kline(count)

    @staticmethod
    def _generate_fallback_kline(count: int) -> pd.DataFrame:
        """Generate mock average-price K-line when APIs are unreachable."""
        import random
        # Use a local Random instance to avoid corrupting the global random state
        rng = random.Random(42)
        base_price = 15.0 + rng.random() * 5
        drift = 0.0001
        volatility = 0.01
        prices = [base_price]
        for _ in range(count):
            prices.append(prices[-1] * (1 + drift + volatility * (rng.random() * 2 - 1)))

        rows = []
        today = datetime.datetime.now()
        for i in range(count):
            close = round(prices[i + 1], 2)
            open_p = round(close * (1 + (rng.random() - 0.5) * 0.015), 2)
            high = round(max(open_p, close) * (1 + rng.random() * 0.01), 2)
            low = round(min(open_p, close) * (1 - rng.random() * 0.01), 2)
            volume = int(30_000_000 + rng.random() * 70_000_000)
            delta = datetime.timedelta(days=count - i)
            rows.append({
                "date": (today - delta).strftime("%Y-%m-%d"),
                "open": open_p, "close": close,
                "high": high, "low": low, "volume": volume,
            })
        df = pd.DataFrame(rows)
        df = df.sort_values("date").reset_index(drop=True)
        return df
=======
        from app.engine.data_engine import data_engine

        try:
            payload = data_engine.get_avg_price_kline(count)
            rows = payload.get("data") if isinstance(payload, dict) else None
            if rows:
                df = pd.DataFrame(rows)
                if not df.empty and "close" in df.columns:
                    return df
        except Exception as e:
            print(f"[MarketEnv] avg price kline unavailable: {e}")

        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    def _load_structure_frame(self, need: int) -> tuple[pd.DataFrame, str, list[str]]:
        """Load OHLC for env scoring. Prefer avg-price; fallback 上证指数.

        Returns (df, source_label, warnings).
        """
        warnings: list[str] = []
        count = max(120, need + 10)
        df = self.get_avg_price_kline(count)
        if df is not None and len(df) >= need:
            df = df.copy()
            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            df = self._drop_outlier_tip(df)
            if len(df) >= need:
                return df, "avg_price", warnings

        warnings.append("平均股价K线不足，改用上证指数做结构代理")
        try:
            from app.engine.data_engine import data_engine
            import datetime as _dt

            end = _dt.datetime.now().strftime("%Y-%m-%d")
            start = (_dt.datetime.now() - _dt.timedelta(days=max(260, need * 2))).strftime(
                "%Y-%m-%d"
            )
            idx = data_engine.get_history_data("000001.SH", start, end)
            if idx is not None and len(idx) >= need:
                df = idx.copy()
                for col in ("open", "high", "low", "close", "volume"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["close"])
                df = self._drop_outlier_tip(df)
                if len(df) >= need:
                    return df, "000001.SH", warnings
        except Exception as e:
            warnings.append(f"上证指数代理也失败: {e}")

        return pd.DataFrame(), "none", warnings
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

    # ── Internal evaluation ─────────────────────────────────────────

    def _evaluate_environment(self) -> dict:
        need = max(settings.MARKET_ENV_MA_PERIOD + 5, 65)
        df, structure_source, load_warnings = self._load_structure_frame(need)
        market_perf = self._market_performance()

        if df is None or len(df) < need:
            return self._env_from_market_only(
                market_perf,
                reason="平均股价与指数结构均不足，仅依据当日指数/板块表现判断",
            )

        ma_period = settings.MARKET_ENV_MA_PERIOD
        slope_lookback = max(3, int(getattr(settings, "MARKET_ENV_SLOPE_LOOKBACK", 5)))
        max_ext = float(getattr(settings, "MARKET_ENV_MAX_EXTENSION_PCT", 8.0)) / 100.0
        caution_ext = float(getattr(settings, "MARKET_ENV_CAUTION_EXTENSION_PCT", 5.0)) / 100.0
        min_vol = float(settings.MARKET_ENV_MIN_VOL_RATIO)

        df["ma5"] = df["close"].rolling(5).mean()
        df["ma10"] = df["close"].rolling(10).mean()
        df["ma20"] = df["close"].rolling(ma_period).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["ma20_slope"] = df["ma20"].diff(slope_lookback)
        df["vol_ma20"] = df["volume"].rolling(settings.MARKET_ENV_VOL_LOOKBACK).mean()
        df["low_10"] = df["low"].rolling(10).min()
        df["high_20"] = df["high"].rolling(20).max()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        avg_price = float(latest["close"])
        ma5 = self._f(latest["ma5"])
        ma10 = self._f(latest["ma10"])
        ma20 = self._f(latest["ma20"])
        ma60 = self._f(latest["ma60"])
        ma20_slope = self._f(latest["ma20_slope"])
        vol_current = self._f(latest["volume"])
        vol_ma = self._f(latest["vol_ma20"]) or 1.0

        dist_ma20 = (avg_price - ma20) / ma20 if ma20 > 0 else 0.0
        above_ma20 = avg_price > ma20 > 0
        above_ma60 = avg_price > ma60 > 0
        ma20_rising = ma20_slope >= 0
        # 归一化斜率：相对 MA20 的百分比变化
        ma20_slope_pct = (ma20_slope / ma20 * 100) if ma20 > 0 else 0.0

        bull_stack = ma5 > 0 and ma10 > 0 and ma20 > 0 and ma5 >= ma10 >= ma20
        soft_stack = ma5 > 0 and ma20 > 0 and ma5 >= ma20
        bear_stack = (
            ma5 > 0 and ma10 > 0 and ma20 > 0 and ma60 > 0
            and ma5 < ma10 < ma20 < ma60
        )

        vol_ratio = vol_current / vol_ma if vol_ma > 0 else 1.0
        vol_healthy = vol_ratio >= min_vol
        vol_dry = vol_ratio < min_vol * 0.85
        # 放量恐慌：量比过高且收阴，偏风险
        bearish_candle = float(latest["close"]) < float(latest.get("open") or latest["close"])
        vol_panic = vol_ratio >= 2.2 and bearish_candle

        # 近端低点抬高（结构未坏）
        low_10 = self._f(latest["low_10"])
        low_prev = self._f(df["low"].iloc[-21:-11].min()) if len(df) >= 21 else low_10
        higher_low = low_10 >= low_prev * 0.995 if low_prev > 0 else True
        # 近 5 日回撤
        high_20 = self._f(latest["high_20"]) or avg_price
        drawdown = (high_20 - avg_price) / high_20 if high_20 > 0 else 0.0

        # 市场表现：多指数 + 板块涨跌广度（赚钱效应）—— 前面已取
        index_bias = market_perf.get("index_bias") or "unknown"
        breadth_bias = market_perf.get("breadth_bias") or "unknown"

        signals: list[str] = []
        warnings: list[str] = []
        checklist: dict = {
            "above_ma20": above_ma20,
            "ma20_rising": ma20_rising,
            "bull_stack": bull_stack,
            "above_ma60": above_ma60,
            "vol_healthy": vol_healthy,
            "higher_low": higher_low,
            "not_overextended": dist_ma20 <= max_ext,
            "index_ok": index_bias != "bear",
            "breadth_ok": breadth_bias != "bear",
        }

        # ── 打分（多头 / 空头）──
        bull_pts = 0.0
        bear_pts = 0.0

        if above_ma20:
            bull_pts += 18
            signals.append("平均股价站稳 MA20")
        else:
            bear_pts += 16
            warnings.append("平均股价跌破 MA20")

        if above_ma60:
            bull_pts += 10
            signals.append("站稳 MA60（中期趋势未坏）")
        else:
            bear_pts += 12
            warnings.append("跌破 MA60")

        if bull_stack:
            bull_pts += 18
            signals.append("短期均线多头排列（MA5≥MA10≥MA20）")
        elif soft_stack:
            bull_pts += 8
            signals.append("价格仍在 MA20 上方（弱多头）")
        if bear_stack:
            bear_pts += 28
            warnings.append("均线空头排列（MA5<MA10<MA20<MA60）")

        if ma20_rising and ma20_slope_pct >= 0.05:
            bull_pts += 14
            signals.append(f"MA20 上行（{slope_lookback}日斜率 {ma20_slope_pct:+.2f}%）")
        elif ma20_rising:
            bull_pts += 6
            signals.append("MA20 走平略上")
        else:
            bear_pts += 14
            warnings.append(f"MA20 下行（{slope_lookback}日斜率 {ma20_slope_pct:+.2f}%）")

        if vol_healthy and not vol_panic:
            bull_pts += 10
            signals.append(f"量能正常（量比 {vol_ratio:.2f}）")
        elif vol_dry:
            bear_pts += 8
            warnings.append(f"成交量萎缩（量比 {vol_ratio:.2f}）")
        if vol_panic:
            bear_pts += 12
            warnings.append(f"放量收阴，情绪偏恐慌（量比 {vol_ratio:.2f}）")

        if higher_low:
            bull_pts += 10
            signals.append("近端低点抬高，结构未坏")
        else:
            bear_pts += 10
            warnings.append("近端低点下移，结构转弱")

        # 伸展 / 过热：离 MA20 太远则扣多头分，并可能禁止开仓
        overheated = dist_ma20 > max_ext
        caution_heat = caution_ext < dist_ma20 <= max_ext
        if overheated:
            bull_pts -= 22
            warnings.append(
                f"平均股价较 MA20 偏离 {dist_ma20 * 100:.1f}%（>{max_ext * 100:.0f}%），过热追高风险"
            )
        elif caution_heat:
            bull_pts -= 8
            warnings.append(
                f"平均股价较 MA20 偏离 {dist_ma20 * 100:.1f}%，追高需谨慎"
            )
        elif 0 <= dist_ma20 <= caution_ext and above_ma20:
            bull_pts += 8
            signals.append(f"回踩/贴近 MA20 区（偏离 {dist_ma20 * 100:.1f}%）")

        if drawdown > 0.08 and not above_ma20:
            bear_pts += 6
            warnings.append(f"自20日高点回撤 {drawdown * 100:.1f}%")

        if index_bias == "bull":
            bull_pts += 10
            signals.append(
                f"主要指数偏多（{market_perf.get('index_summary') or '多指数确认'}）"
            )
        elif index_bias == "bear":
            bear_pts += 12
            warnings.append(
                f"主要指数偏弱（{market_perf.get('index_summary') or '指数下跌'}）"
            )
        elif index_bias == "mixed":
            bear_pts += 4
            warnings.append(
                f"指数风格分化（{market_perf.get('index_summary') or '主板/成长不一致'}）"
            )

        # 板块广度 / 涨跌家数：真实赚钱效应
        if breadth_bias == "bull":
            bull_pts += 12
            signals.append(
                f"板块赚钱效应偏强（{market_perf.get('breadth_summary') or ''}）".rstrip("（）")
            )
        elif breadth_bias == "bear":
            bear_pts += 14
            warnings.append(
                f"板块普跌/涨少跌多（{market_perf.get('breadth_summary') or ''}）".rstrip("（）")
            )
        elif breadth_bias == "mixed":
            bear_pts += 3
            warnings.append(
                f"板块表现一般（{market_perf.get('breadth_summary') or ''}）".rstrip("（）")
            )

        bull_pts = max(0.0, bull_pts)
        bear_pts = max(0.0, bear_pts)

        # 市场表现过弱时，即使均线多头也不开仓
        market_weak = index_bias == "bear" or breadth_bias == "bear"

        # ── 状态裁决 ──
        if bear_stack or (bear_pts >= 40 and bear_pts > bull_pts + 8):
            env_state = "bear"
            can_trade = False
            message = "空头市场 — 禁止开仓"
        elif market_weak and above_ma20 and bull_stack and not overheated:
            env_state = "neutral"
            can_trade = False
            message = "结构偏多但市场表现偏弱 — 暂停开仓"
            warnings.insert(0, "均线结构尚可，但指数/板块赚钱效应不足，不宜新开仓")
        elif (
            above_ma20
            and ma20_rising
            and vol_healthy
            and not overheated
            and not vol_panic
            and not market_weak
            and bull_pts >= 52
            and bull_pts >= bear_pts + 10
            and checklist.get("breadth_ok", True)
            and checklist.get("index_ok", True)
        ):
            env_state = "bull"
            can_trade = True
            message = "多头市场 — 允许开仓"
        elif overheated and above_ma20 and bull_stack:
            env_state = "neutral"
            can_trade = False
            message = "多头过热 — 暂停追高开仓"
            if "过热" not in "".join(warnings):
                warnings.insert(0, "趋势偏多但偏离均线过大，执行器与推荐将锁定新开仓")
        elif (
            # 谨慎开仓：结构未坏、未过热、市场未明显走弱（避免数据缺失/中性就一刀切）
            above_ma20
            and not overheated
            and not vol_panic
            and not market_weak
            and bull_pts >= 38
            and bull_pts >= bear_pts
            and checklist.get("index_ok", True)
        ):
            env_state = "neutral"
            can_trade = True
            message = "震荡偏多 — 允许谨慎开仓"
            warnings.insert(0, "未达强多头标准，建议缩小仓位、提高个股结构门槛")
        else:
            env_state = "neutral"
            can_trade = False
            message = "震荡/观望 — 暂停开仓"

        if load_warnings:
            for w in load_warnings:
                if w not in warnings:
                    warnings.append(w)
        if structure_source and structure_source != "avg_price":
            warnings.append(f"结构数据源：{structure_source}（代理）")

        confidence = round(min(100.0, abs(bull_pts - bear_pts) * 1.2 + 20), 1)
        if structure_source != "avg_price":
            confidence = round(max(0.0, confidence - 15), 1)

        return {
            "env_state": env_state,
            "can_trade": can_trade,
            "avg_price": round(avg_price, 2),
            "ma20": round(ma20, 2),
            "ma20_slope": round(ma20_slope, 4),
            "ma20_slope_pct": round(ma20_slope_pct, 3),
            "ma5": round(ma5, 2),
            "ma10": round(ma10, 2),
            "ma60": round(ma60, 2),
            "dist_ma20_pct": round(dist_ma20 * 100, 2),
            "vol_ratio": round(vol_ratio, 2),
            "volume": int(vol_current),
            "vol_ma20": int(vol_ma) if vol_ma > 0 else 0,
            "bull_score": round(bull_pts, 1),
            "bear_score": round(bear_pts, 1),
            "confidence": confidence,
            "overheated": overheated,
            "checklist": checklist,
            "index_bias": index_bias,
            "breadth_bias": breadth_bias,
            "market_performance": market_perf,
            "structure_source": structure_source,
            "degraded": structure_source != "avg_price",
            "signals": signals[:8],
            "warnings": warnings[:8],
            "message": message,
        }

    def _env_from_market_only(self, market_perf: dict, reason: str) -> dict:
        """Fallback when structure series unavailable.

        Only hard-lock when index/breadth clearly weak. If the tape is not
        bearish, allow cautious opens so a data outage does not freeze the book.
        """
        index_bias = (market_perf or {}).get("index_bias") or "unknown"
        breadth_bias = (market_perf or {}).get("breadth_bias") or "unknown"
        warnings = [reason]
        signals: list[str] = []

        if index_bias == "bear" or breadth_bias == "bear":
            env_state, message = "bear", "市场表现偏弱 — 禁止开仓"
            can_trade = False
            warnings.append("指数或板块赚钱效应偏弱")
        elif index_bias == "unknown" and breadth_bias == "unknown":
            env_state, message = "neutral", "行情数据不足 — 暂停开仓"
            can_trade = False
            warnings.append("指数与板块均不可用，无法判断开仓环境")
        else:
            # 有指数/广度且非明显偏弱 → 允许谨慎开仓（数据故障不应永久锁死）
            env_state = "neutral"
            can_trade = True
            message = "结构数据缺失 — 降级允许谨慎开仓"
            warnings.append("缺少均线结构，已按指数/板块表现降级放行；请提高个股门槛、控制仓位")
            if market_perf.get("index_summary"):
                signals.append(str(market_perf["index_summary"]))

        base = self._empty(message)
        base.update({
            "env_state": env_state,
            "can_trade": can_trade,
            "index_bias": index_bias,
            "breadth_bias": breadth_bias,
            "market_performance": market_perf or {},
            "structure_source": "market_only",
            "degraded": True,
            "confidence": 25.0 if can_trade else 10.0,
            "signals": signals,
            "warnings": warnings[:6],
            "message": message,
        })
        return base

    @staticmethod
    def _f(v) -> float:
        try:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return 0.0
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _empty(msg: str) -> dict:
        return {
            "env_state": "neutral",
            "can_trade": False,
            "avg_price": 0.0,
            "ma20": 0.0,
            "ma20_slope": 0.0,
            "ma20_slope_pct": 0.0,
            "ma5": 0.0,
            "ma10": 0.0,
            "ma60": 0.0,
            "dist_ma20_pct": 0.0,
            "vol_ratio": 0.0,
            "volume": 0,
            "vol_ma20": 0,
            "bull_score": 0.0,
            "bear_score": 0.0,
            "confidence": 0.0,
            "overheated": False,
            "checklist": {},
            "index_bias": "unknown",
            "breadth_bias": "unknown",
            "market_performance": {},
            "signals": [],
            "warnings": [msg],
            "message": msg,
        }

    def _market_performance(self) -> dict:
        """Combine major indices + sector breadth into a market-performance snapshot.

        Uses live Tencent quotes / board data. Failures degrade to unknown —
        never invent numbers.
        """
        out = {
            "index_bias": "unknown",
            "breadth_bias": "unknown",
            "index_summary": "",
            "breadth_summary": "",
            "indices": [],
            "sector_up_ratio": None,
            "stock_up_ratio": None,
            "sector_avg_change": None,
        }
        try:
            from app.engine.data_engine import data_engine

            indices = data_engine._fetch_real_indices() or []
            out["indices"] = [
                {
                    "name": i.get("name"),
                    "code": i.get("code"),
                    "price": i.get("price"),
                    "change_pct": i.get("change_pct"),
                }
                for i in indices
            ]
            changes = [float(i.get("change_pct") or 0) for i in indices if i.get("price")]
            if changes:
                up_n = sum(1 for c in changes if c > 0)
                down_n = sum(1 for c in changes if c < 0)
                avg_chg = sum(changes) / len(changes)
                # 风格：主板(上证/深成) vs 成长(创业/科创)
                main = [float(i.get("change_pct") or 0) for i in indices if i.get("code") in ("000001.SH", "399001.SZ")]
                growth = [float(i.get("change_pct") or 0) for i in indices if i.get("code") in ("399006.SZ", "000688.SH")]
                main_avg = sum(main) / len(main) if main else avg_chg
                growth_avg = sum(growth) / len(growth) if growth else avg_chg
                style_gap = abs(main_avg - growth_avg)

                names = "、".join(
                    f"{i.get('name')}{float(i.get('change_pct') or 0):+.2f}%"
                    for i in indices[:4]
                )
                out["index_summary"] = names

                if up_n >= 3 and avg_chg > 0.15:
                    out["index_bias"] = "bull"
                elif down_n >= 3 and avg_chg < -0.15:
                    out["index_bias"] = "bear"
                elif style_gap >= 1.2 and (main_avg * growth_avg < 0):
                    out["index_bias"] = "mixed"
                elif avg_chg > 0:
                    out["index_bias"] = "bull" if up_n >= 2 else "mixed"
                elif avg_chg < 0:
                    out["index_bias"] = "bear" if down_n >= 2 else "mixed"
                else:
                    out["index_bias"] = "mixed"

            # 板块广度：涨板块占比 + 板块内涨跌家数
            sectors = data_engine.get_sectors(40) or []
            if sectors:
                sec_up = sum(1 for s in sectors if float(s.get("change_pct") or 0) > 0)
                sec_n = len(sectors)
                sec_ratio = sec_up / sec_n if sec_n else 0.0
                sec_avg = sum(float(s.get("change_pct") or 0) for s in sectors) / sec_n
                stock_up = sum(int(s.get("up_count") or 0) for s in sectors)
                stock_tot = sum(int(s.get("total_count") or 0) for s in sectors)
                stock_ratio = (stock_up / stock_tot) if stock_tot > 0 else None

                out["sector_up_ratio"] = round(sec_ratio * 100, 1)
                out["sector_avg_change"] = round(sec_avg, 2)
                out["stock_up_ratio"] = round(stock_ratio * 100, 1) if stock_ratio is not None else None

                parts = [f"涨板块 {sec_up}/{sec_n}"]
                if stock_ratio is not None:
                    parts.append(f"涨跌家数约 {stock_ratio * 100:.0f}%")
                parts.append(f"板块均涨跌 {sec_avg:+.2f}%")
                out["breadth_summary"] = "，".join(parts)

                if sec_ratio >= 0.55 and sec_avg > 0.2 and (stock_ratio is None or stock_ratio >= 0.5):
                    out["breadth_bias"] = "bull"
                elif sec_ratio <= 0.4 or sec_avg < -0.3 or (stock_ratio is not None and stock_ratio < 0.4):
                    out["breadth_bias"] = "bear"
                else:
                    out["breadth_bias"] = "mixed"
        except Exception as e:
            print(f"[MarketEnv] market performance snapshot failed: {e}")
        return out

    def _index_bias(self) -> str:
        """Backward-compatible wrapper."""
        return self._market_performance().get("index_bias") or "unknown"

    @staticmethod
    def _drop_outlier_tip(df: pd.DataFrame, max_day_move: float = 0.05) -> pd.DataFrame:
        """Drop last bar if broad avg-price day move is absurd (intraday sample)."""
        if df is None or len(df) < 3 or "close" not in df.columns:
            return df
        closes = pd.to_numeric(df["close"], errors="coerce")
        if closes.iloc[-2] and float(closes.iloc[-2]) > 0:
            day = float(closes.iloc[-1] / closes.iloc[-2] - 1)
            if abs(day) > max_day_move:
                return df.iloc[:-1].copy()
        return df


market_env_engine = MarketEnvEngine()
