"""Sector Engine (Core 2) — 行业板块筛选排序.

Auto-ranks all A-share industry sectors by trend strength, keeps only
the top-N bullish sectors, and blacklists weak/falling sectors.

Rules from req.txt:
  1. Industry index bullish alignment: 5MA > 10MA > 20MA > 60MA
  2. Sector 20-day return > average stock price 20-day return
  3. Increasing daily-limit-up count within sector (赚钱效应)
  4. Eliminate consistently falling / new-low sectors
"""

import datetime
import time
from typing import Optional

import numpy as np
import pandas as pd

from app.core.config import settings


class SectorEngine:
    """Ranks industry sectors by composite trend-strength score.

    Only the top-N sectors are considered for stock screening;
    the rest are blacklisted to avoid cold/weak sectors.
    """

    def __init__(self):
        self._ranking_cache: list = []
        self._cache_ts: float = 0.0
        self._cache_ttl: float = float(settings.SECTOR_CACHE_TTL)  # seconds

    # ── Public API ──────────────────────────────────────────────────

    def rank_sectors(self, force_refresh: bool = False) -> list:
        """Rank all industry sectors by composite strength score.

        Returns a list of dicts sorted by strength_score descending:
          [{sector_code, sector_name, strength_score, rank,
            ma_alignment, change_20d, limit_up_count, leading_stock, is_blacklisted}, ...]
        """
        now = time.time()
        if not force_refresh and self._ranking_cache and (now - self._cache_ts) < self._cache_ttl:
            return self._ranking_cache

        ranking = self._compute_all_rankings()
        self._ranking_cache = ranking
        self._cache_ts = now
        return ranking

    def get_top_sectors(self, top_n: int = None) -> list:
        """Get the top-N bullish sectors (sorted by score)."""
        if top_n is None:
            top_n = settings.SECTOR_TOP_N
        ranking = self.rank_sectors()
        # Only return non-blacklisted, bullish-aligned sectors
        eligible = [s for s in ranking if not s["is_blacklisted"] and s["ma_alignment"] == "bullish"]
        return eligible[:top_n]

    def get_blacklisted_sectors(self) -> list:
        """Return all currently blacklisted sector codes and names."""
        ranking = self.rank_sectors()
        return [s for s in ranking if s["is_blacklisted"]]

    def is_sector_bullish(self, sector_code: str) -> bool:
        """Check if a specific sector meets the MA-alignment criteria."""
        ranking = self.rank_sectors()
        for s in ranking:
            if s["sector_code"] == sector_code:
                return s["ma_alignment"] == "bullish" and not s["is_blacklisted"]
        return False

    def filter_stocks_by_sector(self, sector_codes: list, limit_per_sector: int = 30) -> list:
        """Get stock symbols belonging to the given top-ranked sectors.

        Returns a deduplicated list of stock symbols like ['000001.SZ', '600519.SH', ...].
        """
        from app.engine.data_engine import data_engine

        all_stocks = []
        seen = set()

        # Build industry → stock mapping once
        industry_map = data_engine._build_industry_map() if hasattr(data_engine, "_build_industry_map") else {}

        for sc in sector_codes:
            # Get sector name from code
            sector_name = None
            ranking = self.rank_sectors()
            for r in ranking:
                if r["sector_code"] == sc:
                    sector_name = r["sector_name"]
                    break
            if not sector_name:
                continue

            # Match to East Money industry
            matched = data_engine._match_industry(sector_name, list(industry_map.keys()))
            if not matched:
                continue

            stocks = industry_map.get(matched, [])
            for sym in stocks[:limit_per_sector]:
                if sym not in seen:
                    all_stocks.append(sym)
                    seen.add(sym)

        return all_stocks

    def get_sector_strength_score(self, sector_code: str) -> float:
        """Return the composite strength score for a single sector."""
        ranking = self.rank_sectors()
        for s in ranking:
            if s["sector_code"] == sector_code:
                return s["strength_score"]
        return 0.0

    # ── Internal computation ────────────────────────────────────────

    def _compute_all_rankings(self) -> list:
        """Fetch sector list, compute K-line indicators for each, score and rank."""
        from app.engine.data_engine import data_engine

        sectors = data_engine.get_sectors(60)  # Get top 60 sectors by daily change
        if not sectors:
            return []

        # Get average stock price 20-day return (benchmark)
        avg_price_change = self._get_avg_price_change_20d()

        results = []
        for idx, sector in enumerate(sectors):
            code = sector.get("code", "")
            name = sector.get("name", "")
            if not code:
                continue

            # Fetch sector index K-line
            kline = self._get_sector_kline(code)
            if kline is None or len(kline) < 60:
                # Insufficient data — score as neutral and continue
                results.append({
                    "sector_code": code,
                    "sector_name": name,
                    "strength_score": 50.0,
                    "rank": idx + 1,
                    "ma_alignment": "unknown",
                    "ma5": 0, "ma10": 0, "ma20": 0, "ma60": 0,
                    "change_20d": sector.get("change_pct", 0),
                    "limit_up_count": sector.get("up_count", 0),
                    "leading_stock": sector.get("leading_stock", ""),
                    "leading_stock_code": sector.get("leading_stock_code", ""),
                    "is_blacklisted": True,
                    "details": {"reason": "K-line 数据不足"},
                })
                continue

            df = pd.DataFrame(kline)
            if len(df) < 60:
                continue

            # ── Calculate MAs ──
            for p in settings.SECTOR_MA_PERIODS:
                df[f"ma{p}"] = df["close"].rolling(window=p).mean()

            latest = df.iloc[-1]
            ma5 = float(latest.get("ma5", 0) or 0)
            ma10 = float(latest.get("ma10", 0) or 0)
            ma20 = float(latest.get("ma20", 0) or 0)
            ma60 = float(latest.get("ma60", 0) or 0)

            # ── MA alignment check ──
            if ma5 > 0 and ma10 > 0 and ma20 > 0 and ma60 > 0:
                if ma5 > ma10 > ma20 > ma60:
                    ma_align = "bullish"
                elif ma5 < ma60 or ma10 < ma60:
                    ma_align = "bearish"
                else:
                    ma_align = "mixed"
            else:
                ma_align = "unknown"

            # ── 20-day return ──
            if len(df) >= 20:
                close_20d_ago = float(df["close"].iloc[-20])
                close_now = float(latest["close"])
                change_20d = round((close_now - close_20d_ago) / close_20d_ago * 100, 2) if close_20d_ago > 0 else 0
            else:
                change_20d = sector.get("change_pct", 0)

            # ── Limit-up stock count (from sector data) ──
            limit_up_count = sector.get("up_count", 0)

            # ── Composite strength score (0-100) ──
            score = self._compute_score(ma_align, change_20d, avg_price_change, limit_up_count)

            # ── Blacklist determination ──
            is_blacklisted = (
                ma_align == "bearish"
                or change_20d < avg_price_change - 5  # >5% below market average
                or ma_align == "unknown"
            )

            results.append({
                "sector_code": code,
                "sector_name": name,
                "strength_score": score,
                "rank": 0,  # will set after sorting
                "ma_alignment": ma_align,
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "change_20d": change_20d,
                "limit_up_count": limit_up_count,
                "leading_stock": sector.get("leading_stock", ""),
                "leading_stock_code": sector.get("leading_stock_code", ""),
                "is_blacklisted": is_blacklisted,
                "details": {
                    "avg_price_change_20d": avg_price_change,
                },
            })

        # Sort by score descending, assign ranks
        results.sort(key=lambda x: x["strength_score"], reverse=True)
        for i, r in enumerate(results):
            r["rank"] = i + 1

        return results

    def _compute_score(self, ma_align: str, change_20d: float,
                       avg_price_change: float, limit_up_count: int) -> float:
        """Compute a 0-100 composite strength score."""
        # MA alignment score (max 40 pts)
        ma_scores = {"bullish": 40, "mixed": 20, "bearish": 5, "unknown": 5}
        ma_score = ma_scores.get(ma_align, 5)

        # Relative performance score (max 30 pts)
        rel_change = change_20d - avg_price_change
        # Clamp between -10 and +15 percentage points of outperformance
        perf_score = max(0, min(30, 15 + rel_change * 2))

        # Money-making effect score (max 20 pts) — based on limit-up count
        # 0 → 0, 5 → 10, 10+ → 20
        lu_score = min(20, limit_up_count * 2)

        # Volume trend bonus (max 10 pts) — placeholder for now
        vol_score = 10  # Could add real volume-trend analysis later

        total = ma_score + perf_score + lu_score + vol_score
        return round(min(100, total), 2)

    @staticmethod
    def _get_avg_price_change_20d() -> float:
        """Get the 20-day return of the average stock price (benchmark)."""
        from app.engine.market_env_engine import market_env_engine

        df = market_env_engine.get_avg_price_kline(30)
        if df is None or len(df) < 20:
            return 0.0
        close_now = float(df["close"].iloc[-1])
        close_20d = float(df["close"].iloc[-20])
        return round((close_now - close_20d) / close_20d * 100, 2) if close_20d > 0 else 0.0

    @staticmethod
    def _get_sector_kline(sector_code: str, count: int = 80) -> list | None:
        """Fetch K-line data for a sector/board index from Tencent.

        Sector K-line uses the same Tencent K-line API with board-specific codes.
        Falls back to simulated data when API is unavailable.
        """
        from app.engine.data_engine import data_engine

        cache_key = f"sec_kline_{sector_code}_{count}"
        cached = data_engine._cache_get(cache_key, "kline")
        if cached:
            return cached

        # Try fetching from Tencent using the board code
        tcode = f"bk{sector_code}" if not sector_code.startswith("bk") else sector_code
        url = (
            f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={tcode},day,,,{count},qfq"
        )
        try:
            data_engine._rate_limit()
            resp = data_engine.http.get(url)
            data = resp.json()
            if isinstance(data, dict) and data.get("code") == 0:
                stock_data = data.get("data", {}).get(tcode, {})
                klines_raw = stock_data.get("qfqday") or stock_data.get("day") or []
                if klines_raw:
                    result = []
                    for row in klines_raw:
                        if len(row) >= 6:
                            result.append({
                                "date": str(row[0])[:10],
                                "open": round(float(row[1]), 2),
                                "close": round(float(row[2]), 2),
                                "high": round(float(row[3]), 2),
                                "low": round(float(row[4]), 2),
                                "volume": int(float(row[5])),
                            })
                    data_engine._cache_set(cache_key, result)
                    return result
        except Exception:
            pass

        # Fallback: generate mock K-line
        mock = data_engine.generate_fallback_kline(f"{sector_code}.BK", "1d", count)
        data_engine._cache_set(cache_key, mock)
        return mock


sector_engine = SectorEngine()
