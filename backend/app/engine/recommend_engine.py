"""Capital-matched short-term stock recommendations.

Quality-first: only recommend names whose recent daily K-line structure
matches a short-hold setup (trend + pullback + volume). Never pad the
list just to fill max_results.

IMPORTANT: This does NOT guarantee profit.
"""

from __future__ import annotations

import datetime
import time
from typing import Optional

import numpy as np
import pandas as pd

from app.engine.fee_engine import fee_engine
from app.engine.trading_engine import LOT_SIZE

# Minimum K-line pattern score (0~100) to enter the recommendation list
_MIN_PATTERN_SCORE = 62


class RecommendEngine:
    def __init__(self):
        self._cache: dict = {}
        self._cache_ttl = 30.0

    def recommend(
        self,
        cash: float,
        *,
        total_equity: Optional[float] = None,
        max_position_pct: float = 0.25,
        budget_amount: Optional[float] = None,
        max_results: int = 8,
        hold_days_hint: int = 7,
        min_rr: float = 1.5,
        universe_limit: int = 80,
        use_cache: bool = True,
        use_llm: bool = False,
        llm_provider: Optional[str] = None,
        llm_providers: Optional[list] = None,
    ) -> dict:
        """Scan real daily K-lines; return only quality short-hold setups."""
        cash = max(float(cash), 0.0)
        equity = max(float(total_equity) if total_equity is not None else cash, cash)
        pct = max(0.05, min(float(max_position_pct), 1.0))
        min_rr = max(1.0, float(min_rr))
        if budget_amount is not None and float(budget_amount) > 0:
            budget = min(float(budget_amount), equity)
            sizing_mode = "amount"
        else:
            budget = cash * pct
            sizing_mode = "full" if pct >= 0.999 else "pct"

        buy_budget = min(budget, cash)

        from app.engine.market_env_engine import market_env_engine
        from app.engine.strategy_health_engine import strategy_health_engine

        env = market_env_engine.check_environment()
        env_state = env.get("env_state") or "neutral"
        open_allowed = bool(env.get("can_trade"))

        cache_key = (
            f"recq_{round(cash, 2)}_{round(equity, 2)}_{round(buy_budget, 2)}_"
            f"{round(pct, 4)}_{sizing_mode}_{max_results}_{hold_days_hint}_{round(min_rr, 2)}_"
            f"{env_state}_{int(open_allowed)}"
        )
        if use_cache and not use_llm:
            cached = self._cache.get(cache_key)
            if cached and time.time() - cached["_ts"] < self._cache_ttl:
                return cached["data"]

        # Align with strategy_executor: bear / neutral lock new buys
        health = strategy_health_engine.get_health(env_state=env_state)
        if not open_allowed:
            reason = (
                f"大盘环境为「{env.get('message') or env_state}」，"
                "与实盘执行器一致：暂不给出新开仓推荐。"
            )
            if env.get("warnings"):
                reason += " " + "；".join(env["warnings"][:2])
            data = {
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "cash": round(cash, 2),
                "total_equity": round(equity, 2),
                "budget_per_name": round(buy_budget, 2),
                "budget_requested": round(budget, 2),
                "max_position_pct": pct,
                "budget_amount": round(budget, 2) if sizing_mode == "amount" else None,
                "sizing_mode": sizing_mode,
                "hold_days_hint": hold_days_hint,
                "min_risk_reward": min_rr,
                "min_pattern_score": _MIN_PATTERN_SCORE,
                "quality_policy": "env_gate_aligned_with_executor",
                "open_allowed": False,
                "open_policy": "blocked",
                "market_env": {
                    "env_state": env.get("env_state"),
                    "can_trade": env.get("can_trade"),
                    "message": env.get("message"),
                    "warnings": env.get("warnings") or [],
                    "signals": env.get("signals") or [],
                },
                "strategy_health": health,
                "disclaimer": (
                    "本推荐不构成投资建议。当前大盘环境与策略执行器一致锁定新开仓；"
                    "策略健康度仅供观察，不会为凑条数而降门槛。"
                ),
                "scan_stats": {
                    "universe": 0,
                    "scanned": 0,
                    "qualified": 0,
                    "skipped": {"env_blocked": 1},
                },
                "empty_reason": reason,
                "recommendations": [],
                "data_source": "realtime",
                "llm": {"enabled": False},
            }
            if not use_llm:
                self._cache[cache_key] = {"_ts": time.time(), "data": data}
            return data

        # In bull / cautious-open market, require base pattern score; health further weights
        min_score = _MIN_PATTERN_SCORE
        if env.get("degraded") or env_state == "neutral":
            # Degraded / cautious open → slightly stricter stock filter
            min_score = _MIN_PATTERN_SCORE + 5

        max_px = (buy_budget / LOT_SIZE) if buy_budget > 0 else None
        symbols = self._build_universe(universe_limit, max_price=max_px)

        # Batch realtime quotes once — limit-up filter without N HTTP roundtrips
        from app.engine.data_engine import data_engine

        quote_map = {}
        try:
            quote_map = data_engine.get_realtime_quotes_batch(symbols) or {}
        except Exception as e:
            print(f"[Recommend] batch quotes skipped: {e}")

        candidates: list[dict] = []
        scanned = 0
        skipped = {
            "no_data": 0,
            "cannot_afford": 0,
            "weak_setup": 0,
            "poor_rr": 0,
            "low_score": 0,
            "cold_strategy": 0,
            "limit_untradable": 0,
            "weak_rs": 0,
        }
        bench_ret_5 = self._benchmark_ret_5d()

        for sym in symbols:
            scanned += 1
            try:
                item = self._evaluate_kline(
                    sym,
                    buy_budget,
                    cash,
                    hold_days_hint,
                    min_rr,
                    min_score,
                    bench_ret_5=bench_ret_5,
                    quote=quote_map.get(sym),
                )
            except Exception:
                skipped["no_data"] += 1
                continue
            if item is None:
                skipped["weak_setup"] += 1
                continue
            reason = item.pop("_skip", None)
            if reason == "cannot_afford":
                skipped["cannot_afford"] += 1
                continue
            if reason == "poor_rr":
                skipped["poor_rr"] += 1
                continue
            if reason == "low_score":
                skipped["low_score"] += 1
                continue
            if reason == "limit_untradable":
                skipped["limit_untradable"] += 1
                continue
            if reason == "weak_rs":
                skipped["weak_rs"] += 1
                continue
            candidates.append(item)

        # Strategy health weighting: cold strategies heavily discounted / dropped
        for c in candidates:
            st = (c.get("suggested_strategy") or {}).get("type")
            w = strategy_health_engine.weight_for(health, st)
            status = strategy_health_engine.status_for(health, st)
            c["strategy_health_status"] = status
            c["strategy_health_weight"] = w
            base = float(c.get("score") or 0)
            c["adjusted_score"] = round(base * w, 2)
            hinfo = (health.get("strategies") or {}).get(st or "") or {}
            if hinfo.get("reason"):
                reasons = list(c.get("reasons") or [])
                reasons.insert(1, f"策略健康：{hinfo.get('name') or st}（{status}）")
                c["reasons"] = reasons[:6]

        kept = []
        for c in candidates:
            status = c.get("strategy_health_status")
            w = float(c.get("strategy_health_weight") or 0)
            # Drop cold with very low weight
            if status == "cold" and w < 0.35:
                skipped["cold_strategy"] += 1
                continue
            kept.append(c)

        kept.sort(
            key=lambda x: (
                -float(x.get("adjusted_score") or 0),
                -float(x.get("score") or 0),
            )
        )
        # Quality only — never pad; may return fewer than max_results
        top = kept[:max_results]
        for i, c in enumerate(top, 1):
            c["rank"] = i

        empty_reason = None
        if not top:
            empty_reason = self._explain_empty(skipped, buy_budget, cash, env, min_score)
            if skipped.get("cold_strategy"):
                empty_reason += "；匹配策略近期健康度偏低已过滤"

        data = {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "cash": round(cash, 2),
            "total_equity": round(equity, 2),
            "budget_per_name": round(buy_budget, 2),
            "budget_requested": round(budget, 2),
            "max_position_pct": pct,
            "budget_amount": round(budget, 2) if sizing_mode == "amount" else None,
            "sizing_mode": sizing_mode,
            "hold_days_hint": hold_days_hint,
            "min_risk_reward": min_rr,
            "min_pattern_score": min_score,
            "quality_policy": "kline_sector_rs_limit_exit_plus_env_health",
            "open_allowed": True,
            "open_policy": "open",
            "market_env": {
                "env_state": env.get("env_state"),
                "can_trade": env.get("can_trade"),
                "message": env.get("message"),
                "warnings": env.get("warnings") or [],
                "signals": env.get("signals") or [],
            },
            "strategy_health": health,
            "disclaimer": (
                "本推荐不构成投资建议，更不保证盈利。"
                "流程：大盘允许开仓 → 强势板块宇宙 → 涨停/一字板过滤 → "
                "日K回踩结构+相对强弱 → 分层退出计划 → 策略健康加权；宁缺毋滥。"
            ),
            "scan_stats": {
                "universe": len(symbols),
                "scanned": scanned,
                "qualified": len(kept),
                "skipped": skipped,
            },
            "empty_reason": empty_reason,
            "recommendations": top,
            "data_source": "realtime",
        }
        if use_llm:
            from app.engine.llm_engine import llm_engine
            data = llm_engine.enrich_recommendations(
                data,
                provider=llm_provider,
                providers=llm_providers,
            )
        else:
            data["llm"] = {"enabled": False}

        if not use_llm:
            self._cache[cache_key] = {"_ts": time.time(), "data": data}
        return data

    @staticmethod
    def _explain_empty(skipped: dict, budget: float, cash: float, env: dict, min_score: int) -> str:
        afford = skipped.get("cannot_afford", 0)
        weak = skipped.get("weak_setup", 0)
        poor = skipped.get("poor_rr", 0)
        low = skipped.get("low_score", 0)
        no_data = skipped.get("no_data", 0)
        limit_u = skipped.get("limit_untradable", 0)
        weak_rs = skipped.get("weak_rs", 0)
        parts = ["当前没有达到 K 线结构门槛的短线标的（宁缺毋滥）"]
        if env.get("env_state") == "bear":
            parts.append(f"大盘偏空，结构分需≥{min_score}")
        dominant = max(
            ("买不起一手", afford),
            ("K线结构不合格", weak + low),
            ("盈亏比不足", poor),
            ("涨停/不可交易", limit_u),
            ("弱于大盘相对强弱", weak_rs),
            ("行情缺失", no_data),
            key=lambda x: x[1],
        )
        if dominant[1] > 0:
            parts.append(f"主要原因：{dominant[0]}")
        if afford >= weak and afford > 0:
            parts.append(f"单票预算约 ¥{budget:,.0f}，可提高仓位或改全仓")
        elif poor > 0 and poor >= low:
            parts.append("可适当降低最低盈亏比后再试")
        return "；".join(parts)

    @staticmethod
    def _benchmark_ret_5d() -> Optional[float]:
        """5-day market benchmark return for relative strength.

        Prefer 上证指数; fallback to avg-price with outlier guard (intraday
        incomplete avg samples can spike and break RS).
        """
        from app.engine.data_engine import data_engine

        end = datetime.datetime.now().strftime("%Y-%m-%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")

        def _ret5_from_closes(closes: pd.Series) -> Optional[float]:
            closes = pd.to_numeric(closes, errors="coerce").dropna()
            if len(closes) < 6:
                return None
            # Drop incomplete/outlier last bar (>5% day move on broad index/avg)
            day = float(closes.iloc[-1] / closes.iloc[-2] - 1)
            if abs(day) > 0.05:
                closes = closes.iloc[:-1]
            if len(closes) < 6:
                return None
            ret = float(closes.iloc[-1] / closes.iloc[-6] - 1)
            # Sanity: broad market 5d move beyond ±15% is data garbage for RS
            if abs(ret) > 0.15:
                return None
            return ret

        try:
            idx = data_engine.get_history_data("000001.SH", start, end)
            if idx is not None and len(idx) >= 6:
                r = _ret5_from_closes(idx["close"])
                if r is not None:
                    return r
        except Exception:
            pass

        try:
            from app.engine.market_env_engine import market_env_engine

            df = market_env_engine.get_avg_price_kline(30)
            if df is None or len(df) < 6:
                return None
            return _ret5_from_closes(df["close"])
        except Exception:
            return None

    def _build_universe(self, limit: int, max_price: Optional[float] = None) -> list:
        from app.engine.data_engine import data_engine

        symbols: list[str] = []
        seen: set[str] = set()

        def _add(code: Optional[str]) -> None:
            if not code or code in seen:
                return
            seen.add(code)
            symbols.append(code)

        def _is_st_name(name: str) -> bool:
            return "ST" in (name or "").upper() or "退" in (name or "")

        # ── Hard sector gate (invest-a-share): prefer top bullish sectors ──
        sector_ok = False
        try:
            from app.engine.sector_engine import sector_engine

            top = sector_engine.get_top_sectors(8) or []
            # No fully-bullish sectors → non-blacklisted; still empty → top by score
            if not top:
                ranking = sector_engine.rank_sectors() or []
                top = [s for s in ranking if not s.get("is_blacklisted")][:8]
            if not top:
                ranking = sector_engine.rank_sectors() or []
                top = ranking[:8]
            if top:
                codes = [s.get("sector_code") for s in top if s.get("sector_code")]
                sector_stocks = sector_engine.filter_stocks_by_sector(
                    codes, limit_per_sector=12
                )
                # Prefer cheaper boards when budget-constrained
                ordered = list(sector_stocks or [])
                if max_price and max_price > 0:
                    cheap, rest = [], []
                    for code in ordered:
                        bare = str(code).split(".")[0]
                        if bare.startswith(("00", "30")) or str(code).endswith(".SZ"):
                            cheap.append(code)
                        else:
                            rest.append(code)
                    ordered = cheap + rest
                for code in ordered:
                    _add(code)
                    if len(symbols) >= limit:
                        break
                sector_ok = len(symbols) > 0
                if sector_ok:
                    print(
                        f"[Recommend] universe from {len(top)} ranked sectors: "
                        f"{len(symbols)} symbols"
                    )
        except Exception as e:
            print(f"[Recommend] sector hard gate skipped: {e}")

        # Fallback only when sector universe empty (data outage)
        if not sector_ok:
            try:
                data_engine.ensure_symbol_list()
            except Exception as e:
                print(f"[Recommend] real stock list unavailable: {e}")
                return []

            pool = [s for s in getattr(data_engine, "_symbols", []) if isinstance(s, dict)]
            cleaned = []
            for s in pool:
                if _is_st_name(str(s.get("name") or "")):
                    continue
                cleaned.append(s)
            pool = cleaned
            if max_price and max_price > 0:
                cheap, rest = [], []
                for s in pool:
                    code = s.get("code") or ""
                    if code.endswith(".SZ") or code.split(".")[0].startswith(("00", "30")):
                        cheap.append(s)
                    else:
                        rest.append(s)
                pool = cheap + rest

            for s in pool:
                _add(s.get("code"))
                if len(symbols) >= limit:
                    break
            print(f"[Recommend] sector empty — fallback general pool: {len(symbols)}")

        return symbols[:limit]

    @staticmethod
    def _turnover(close: float, volume: float) -> float:
        raw = float(volume) * float(close)
        if raw <= 0:
            return 0.0
        if raw < 5_000_000:
            return raw * 100
        return raw

    @staticmethod
    def _limit_untradable(symbol: str, quote: Optional[dict] = None) -> bool:
        """True if near daily limit / one-word board / zero price (untradable)."""
        from app.engine.data_engine import data_engine

        q = quote
        if not q:
            try:
                q = data_engine.get_realtime_quote(symbol)
            except Exception:
                return False
        if not q:
            return False
        name = str(q.get("name") or "")
        if "ST" in name.upper() or "退" in name:
            return True
        price = float(q.get("current_price") or 0)
        if price <= 0:
            return True
        limit_pct = float(data_engine._daily_limit(symbol))
        chg = float(q.get("change_pct") or 0)
        # ≥95% of board limit → treat as untradable chase
        if chg >= limit_pct * 0.95:
            return True
        pre = float(q.get("pre_close") or 0)
        op = float(q.get("open") or 0)
        if pre > 0 and op > 0:
            open_chg = (op / pre - 1.0) * 100.0
            # 一字/开盘即涨停
            if open_chg >= limit_pct * 0.95 and chg >= limit_pct * 0.90:
                return True
        return False

    def _evaluate_kline(
        self,
        symbol: str,
        budget: float,
        cash: float,
        hold_days: int,
        min_rr: float,
        min_score: float,
        bench_ret_5: Optional[float] = None,
        quote: Optional[dict] = None,
    ) -> Optional[dict]:
        """Score one symbol from real daily K-line structure (right-side style)."""
        from app.engine.data_engine import data_engine

        end = datetime.datetime.now().strftime("%Y-%m-%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
        df = data_engine.get_history_data(symbol, start, end)
        if df is None or len(df) < 60:
            return None

        df = df.copy()
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close", "volume"])
        if len(df) < 60:
            return None

        df["ma5"] = df["close"].rolling(5).mean()
        df["ma10"] = df["close"].rolling(10).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["ma20_slope"] = df["ma20"].diff(3)
        df["vol_ma20"] = df["volume"].rolling(20).mean()
        df["vol_ratio"] = df["volume"] / df["vol_ma20"].replace(0, np.nan)
        tr = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"] - df["close"].shift(1)).abs(),
            ),
        )
        df["atr"] = tr.rolling(14).mean()
        df["high_20"] = df["high"].rolling(20).max()
        df["low_10"] = df["low"].rolling(10).min()

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        close = float(latest["close"])
        atr = float(latest["atr"]) if not pd.isna(latest["atr"]) else 0.0
        if close <= 0 or atr <= 0:
            return None

        if fee_engine.buy_cost(close, LOT_SIZE) > min(budget, cash) + 1e-6:
            return {"_skip": "cannot_afford"}

        # Hard filter: limit-up / one-word board (invest-a-share)
        if self._limit_untradable(symbol, quote=quote):
            return {"_skip": "limit_untradable"}

        ma5 = float(latest["ma5"] or 0)
        ma10 = float(latest["ma10"] or 0)
        ma20 = float(latest["ma20"] or 0)
        ma60 = float(latest["ma60"] or 0)
        ma20_slope = float(latest["ma20_slope"] or 0)
        vol = float(latest["volume"] or 0)
        vol_ma = float(latest["vol_ma20"] or 0)
        vol_ratio = float(latest["vol_ratio"]) if not pd.isna(latest["vol_ratio"]) else 0.0
        open_p = float(latest["open"] or close)
        high_20 = float(latest["high_20"] or close)
        low_10 = float(latest["low_10"] or close)

        ret_5 = float(df["close"].iloc[-1] / df["close"].iloc[-6] - 1) if len(df) >= 6 else 0.0
        ret_10 = float(df["close"].iloc[-1] / df["close"].iloc[-11] - 1) if len(df) >= 11 else 0.0
        dist_ma20 = abs(close - ma20) / ma20 if ma20 > 0 else 1.0
        drawdown = (high_20 - close) / high_20 if high_20 > 0 else 0.0
        bullish_candle = close > open_p
        vol_expand = vol > float(prev["volume"] or 0) * 1.3
        # 近5日是否出现缩量（回踩阶段）
        recent_vol = df["vol_ratio"].tail(6).iloc[:-1]
        had_shrink = bool((recent_vol < 0.7).any()) if len(recent_vol) else False
        # 近10日低点抬高（结构未坏）
        low_prev = float(df["low"].iloc[-11:-1].min()) if len(df) >= 11 else low_10
        higher_low = low_10 >= low_prev * 0.995
        turnover = self._turnover(close, vol_ma if vol_ma > 0 else vol)
        liquid = turnover >= 20_000_000

        # Relative strength vs avg-price breadth (skip false strength)
        rs_5 = None
        if bench_ret_5 is not None:
            rs_5 = ret_5 - float(bench_ret_5)
            if rs_5 < -0.02:
                return {"_skip": "weak_rs"}

        # ── Hard K-line gates (must hold) ──
        if not liquid:
            return None
        if ma20 <= 0 or ma60 <= 0:
            return None
        if close < ma60:  # 长期趋势破坏
            return None
        if ma20_slope < 0 and close < ma20:  # 均线下行且跌破，不做
            return None
        if drawdown < 0.005 and dist_ma20 > 0.06:  # 远离均线追高
            return None
        if (close - ma20) / ma20 > 0.12:  # 过度伸展
            return None

        # invest-a-share: pullback within ~2% of MA20, or reclaim day
        near_ma20 = dist_ma20 <= 0.02
        trend_stack = ma5 >= ma10 >= ma20 and close >= ma20
        reclaim = close >= ma20 and float(prev["close"]) < ma20 * 1.005
        if not (near_ma20 or reclaim):
            return None
        # Volume: shrink on pullback OR expand on reclaim (soft hard-gate)
        if not (had_shrink or (reclaim and vol_expand)):
            return None

        # ── Pattern score + reasons (distinctive first, then shared checklist) ──
        score = 0.0
        shared: list[str] = []
        distinct: list[str] = []

        if trend_stack:
            score += 22
            shared.append("短期均线多头排列")
        elif close > ma20 and ma5 > ma20:
            score += 12
            shared.append("价格站稳MA20上方")

        if ma20_slope >= 0:
            score += 10
            shared.append("MA20走平/向上")
        elif ma20_slope > -ma20 * 0.002:
            score += 4

        if near_ma20:
            score += 16
            distinct.append(f"距MA20约 {dist_ma20 * 100:.1f}%（回踩区）")
        elif reclaim:
            score += 14
            distinct.append("收盘重新站回MA20")

        if close > ma60:
            score += 8
            shared.append("站稳MA60")

        if had_shrink:
            score += 10
            distinct.append("回踩段出现缩量")

        if bullish_candle and vol_expand:
            score += 12
            prev_vol = float(prev["volume"] or 0)
            if prev_vol > 0:
                distinct.append(f"放量确认（量比昨约 {vol / prev_vol:.1f}x）")
            else:
                distinct.append("放量阳线确认")
        elif bullish_candle:
            score += 5
            shared.append("收阳线")

        if higher_low:
            score += 8
            shared.append("近端低点抬高")

        if 0.01 <= drawdown <= 0.12:
            score += 6
            distinct.append(f"自20日高点回撤 {drawdown * 100:.1f}%")
        elif drawdown > 0.12:
            score -= 6
            distinct.append(f"回撤偏深 {drawdown * 100:.1f}%")

        if 0 <= ret_5 <= 0.08:
            score += 6
            distinct.append(f"近5日 {ret_5 * 100:+.1f}%")
        elif ret_5 > 0.12:
            score -= 8
            distinct.append(f"近5日偏热 {ret_5 * 100:+.1f}%")
        elif ret_5 < -0.06:
            score -= 5
            distinct.append(f"近5日偏弱 {ret_5 * 100:+.1f}%")
        else:
            distinct.append(f"近5日 {ret_5 * 100:+.1f}%")

        if rs_5 is not None:
            if rs_5 >= 0.02:
                score += 8
                distinct.append(f"5日相对强弱 +{rs_5 * 100:.1f}%")
            elif rs_5 >= 0:
                score += 4
                distinct.append(f"5日相对强弱持平/略强（{rs_5 * 100:+.1f}%）")
            else:
                score -= 2
                distinct.append(f"5日相对强弱略弱 {rs_5 * 100:.1f}%")

        if liquid:
            score += 6

        score = round(max(0.0, min(100.0, score)), 1)
        if score < min_score:
            return {"_skip": "low_score", "score": score}

        # ── Stops from K-line structure (swing low / ATR) ──
        structure_stop = min(low_10 * 0.995, close - 1.2 * atr)
        structure_stop = max(structure_stop, close * 0.94)  # 短线止损不过深
        risk = close - structure_stop
        if risk <= close * 0.008:
            return None
        # 目标：前高附近或 RR 几何
        reward_to_high = max(high_20 - close, 0.0)
        reward = max(reward_to_high * 0.85, 1.6 * atr, risk * min_rr)
        rr = reward / risk
        if rr < min_rr:
            return {"_skip": "poor_rr"}
        target = close + reward
        half_target = close + reward * 0.55

        qty = self._affordable_qty(close, min(budget, cash))
        if qty < LOT_SIZE:
            return {"_skip": "cannot_afford"}
        fees = fee_engine.calculate("buy", close, qty)
        cost = fees.amount + fees.total
        if cost > cash + 1e-6:
            qty = self._affordable_qty(close, cash * 0.98)
            if qty < LOT_SIZE:
                return {"_skip": "cannot_afford"}
            fees = fee_engine.calculate("buy", close, qty)
            cost = fees.amount + fees.total

        name = (
            data_engine.lookup_stock_name(symbol)
            if hasattr(data_engine, "lookup_stock_name")
            else symbol
        )

        strategy = self._match_strategy(
            {
                "trend_stack": trend_stack,
                "near_ma20": near_ma20,
                "ma20_rising": ma20_slope >= 0,
                "above_ma60": close > ma60,
                "vol_shrink_then_expand": had_shrink and vol_expand,
                "had_shrink": had_shrink,
                "higher_low": higher_low,
                "bullish_confirm": bullish_candle and vol_expand,
                "reclaim": reclaim,
                "drawdown": drawdown,
                "ret_10": ret_10,
            }
        )

        exit_plan = {
            "stop_loss": round(structure_stop, 3),
            "take_profit": round(target, 3),
            "take_profit_half": round(half_target, 3),
            "trail_ref_ma5": round(ma5, 3) if ma5 > 0 else None,
            "trail_atr": round(close - 1.5 * atr, 3),
            "time_stop_days": int(hold_days),
            "rules": [
                f"触及半仓目标 {half_target:.2f} 可减半仓锁定利润",
                f"剩余仓位跌破 MA5（{ma5:.2f}）或 ATR 跟踪位离场",
                f"硬止损 {structure_stop:.2f}，不摊薄",
                f"持有约 {hold_days} 个交易日未达标则减仓复核",
            ],
        }

        # 差异化理由在前，共性 checklist 在后（前端只展示前几条）
        reasons = [
            f"匹配「{strategy['name']}」",
            f"盈亏比 {rr:.1f}:1（止损{structure_stop:.2f}/目标{target:.2f}）",
            *distinct,
            *shared,
        ]
        # 去重保序
        seen = set()
        reasons = [r for r in reasons if not (r in seen or seen.add(r))][:6]

        return {
            "symbol": symbol,
            "name": name,
            "price": round(close, 3),
            "suggested_quantity": int(qty),
            "suggested_lots": int(qty // LOT_SIZE),
            "estimated_cost": round(cost, 2),
            "fee_total": round(fees.total, 2),
            "cash_usage_pct": round(cost / cash * 100, 2) if cash > 0 else 0,
            "stop_loss": round(structure_stop, 3),
            "take_profit": round(target, 3),
            "stop_loss_pct": round((structure_stop / close - 1) * 100, 2),
            "take_profit_pct": round((target / close - 1) * 100, 2),
            "risk_reward": round(rr, 2),
            "risk_amount": round(risk * qty, 2),
            "reward_amount": round(reward * qty, 2),
            "atr": round(atr, 3),
            "ret_5d_pct": round(ret_5 * 100, 2),
            "ret_10d_pct": round(ret_10 * 100, 2),
            "rs_5d_pct": round(rs_5 * 100, 2) if rs_5 is not None else None,
            "near_ma20": near_ma20,
            "hold_days_hint": hold_days,
            "score": score,
            "pattern": {
                "trend_stack": trend_stack,
                "near_ma20": near_ma20,
                "ma20_rising": ma20_slope >= 0,
                "above_ma60": close > ma60,
                "vol_shrink_then_expand": had_shrink and vol_expand,
                "higher_low": higher_low,
                "bullish_confirm": bullish_candle and vol_expand,
            },
            "suggested_strategy": strategy,
            "exit_plan": exit_plan,
            "reasons": reasons[:6],
            "action_plan": (
                f"日K结构分 {score}，匹配策略「{strategy['name']}」。"
                f"建议买入 {int(qty)} 股；止损 {structure_stop:.2f}；"
                f"半仓目标 {half_target:.2f} / 满仓目标 {target:.2f}；"
                f"计划持有约 {hold_days} 个交易日。"
                f"跌破 MA5 或硬止损离场，不摊薄成本。"
                f"{strategy.get('playbook', '')}"
            ),
        }

    @staticmethod
    def _match_strategy(pattern: dict) -> dict:
        """Map K-line pattern to the best-fit executable strategy.

        Scoring (not fixed if-else) so deep pullbacks → 龙回头,
        confirm-day bounce → 右侧入场, MA-stack continuation → 趋势跟踪.
        """
        near = bool(pattern.get("near_ma20"))
        shrink = bool(pattern.get("had_shrink"))
        expand = bool(pattern.get("bullish_confirm"))
        trend = bool(pattern.get("trend_stack"))
        rising = bool(pattern.get("ma20_rising"))
        above60 = bool(pattern.get("above_ma60"))
        reclaim = bool(pattern.get("reclaim"))
        higher_low = bool(pattern.get("higher_low"))
        dd = float(pattern.get("drawdown") or 0)
        ret10 = float(pattern.get("ret_10") or 0)

        catalog = {
            "right_side_entry": {
                "type": "right_side_entry",
                "name": "右侧入场策略",
                "why": "回踩后缩量止跌并放量确认，适合右侧跟随",
                "playbook": "操作要点：等收盘确认站稳MA20再介入；跌破MA20×0.98减仓。",
            },
            "dragon_pullback": {
                "type": "dragon_pullback",
                "name": "龙回头策略",
                "why": "阶段高点后缩量回踩均线，偏强势股回调承接",
                "playbook": "操作要点：分批在均线支撑接；跌破回踩低点止损。",
            },
            "trend_following": {
                "type": "trend_following",
                "name": "趋势跟踪策略",
                "why": "均线多头排列且斜率向上，适合沿趋势持有",
                "playbook": "操作要点：沿均线持有；均线死叉或ATR止损离场。",
            },
        }

        scored: list[tuple[float, str]] = []

        # ── 龙回头：回撤更深、贴近均线缩量（可未放量确认）──
        if near and shrink and above60 and dd >= 0.045:
            pts = 50.0 + min(30.0, dd * 250.0)
            if ret10 > -0.05:
                pts += 8
            if not expand:
                pts += 14  # 仍在缩量回踩段，更像龙回头等待
            else:
                pts += 4
            if higher_low:
                pts += 8
            if reclaim:
                pts += 5
            scored.append((pts, "dragon_pullback"))

        # ── 右侧入场：缩量后再放量阳线确认（健康回撤，非深跌）──
        if (near or reclaim) and shrink and expand and above60:
            pts = 48.0
            if reclaim:
                pts += 16
            if 0.01 <= dd <= 0.055:
                pts += 14
            if higher_low:
                pts += 8
            if dd >= 0.08:
                pts -= 22  # 过深交给龙回头
            if dd < 0.01 and not reclaim:
                pts -= 8
            scored.append((pts, "right_side_entry"))

        # ── 趋势跟踪：多头排列延续，回撤浅、非「缩量+放量确认」日──
        if trend and rising and above60:
            pts = 40.0
            if dd < 0.035:
                pts += 20
            if not near:
                pts += 14  # 已离开均线上方运行
            elif not shrink:
                pts += 10
            if near and shrink and expand:
                pts -= 28  # 明显是右侧确认形态
            if dd >= 0.06:
                pts -= 24
            if higher_low:
                pts += 4
            scored.append((pts, "trend_following"))

        if not scored:
            fallback = catalog["right_side_entry"].copy()
            fallback["why"] = "未命中鲜明形态，默认按右侧确认框架谨慎操作"
            return fallback

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_type = scored[0][1]
        result = catalog[best_type].copy()
        # Attach brief score hint for debugging / action_plan richness
        result["match_score"] = round(scored[0][0], 1)
        return result


    @staticmethod
    def _affordable_qty(price: float, budget: float) -> float:
        if price <= 0 or budget <= 0:
            return 0.0
        lots = int((budget / price) // LOT_SIZE)
        while lots > 0:
            qty = float(lots * LOT_SIZE)
            if fee_engine.buy_cost(price, qty) <= budget + 1e-6:
                return qty
            lots -= 1
        return 0.0


recommend_engine = RecommendEngine()
