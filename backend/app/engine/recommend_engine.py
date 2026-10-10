"""Capital-matched short-term stock recommendations.

Quality-first dual path:
  - Bull / normal: trend pullback + volume (right-side)
  - Weak market: also risk-controlled dip-bounce (抄底反弹)

Never pad the list just to fill max_results. IMPORTANT: not a profit guarantee.
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

        from app.engine.market_env_engine import market_env_engine
        from app.engine.market_forecast_engine import market_forecast_engine
        from app.engine.strategy_health_engine import strategy_health_engine

        env = market_env_engine.check_environment()
        forecast = market_forecast_engine.forecast(horizon_days=max(5, int(hold_days_hint)))
        env_state = env.get("env_state") or "neutral"
        open_allowed = bool(env.get("can_trade"))
        overheated = bool(env.get("overheated"))
        f_score = float(forecast.get("forecast_score") or 50)
        f_bias = forecast.get("horizon_bias") or "neutral"
        f_exposure = float(forecast.get("exposure_mult") or 0.7)
        env_exposure = float(env.get("exposure_mult") if env.get("exposure_mult") is not None else (
            1.0 if open_allowed else 0.0
        ))
        checklist = env.get("checklist") or {}
        shallow_pullback = bool(checklist.get("shallow_pullback"))
        days_below = int(env.get("days_below_ma20") or checklist.get("days_below_ma20") or 0)
        top_risk = float(forecast.get("top_risk") or 0)

        # Recommend ≠ auto-executor. Forecast is the short-hold compass;
        # env.can_trade only pauses the auto executor. A weak index day still
        # has RS leaders — do not freeze the recommend book.
        forecast_collapsed = f_score < 25 or (env_state == "bear" and f_bias == "bear" and f_score < 38)
        if forecast_collapsed:
            open_policy = "defensive"
        elif overheated or f_score < 38 or top_risk >= 60:
            open_policy = "defensive"
        elif (
            not open_allowed
            or env_state == "bear"
            or shallow_pullback
            or days_below >= 3
            or env.get("degraded")
            or env_state == "neutral"
            or f_bias == "neutral"
            or f_score < 60
        ):
            open_policy = "cautious"
        else:
            open_policy = "open"

        if open_allowed and env_state == "bull" and (f_score < 45 or top_risk >= 60):
            open_policy = "defensive"

        allow_dip = (
            open_policy in ("defensive", "cautious")
            or shallow_pullback
            or days_below >= 2
            or f_bias == "bear"
            or f_score < 55
            or env_state == "bear"
        )
        # Dip-first only when the tape is actually washing, not when executor is merely paused
        prefer_dip = (shallow_pullback or days_below >= 3) and f_score < 48
        allow_rs = f_score >= 32 and f_bias != "bear"

        # Base pattern score; keep floors tradable — daily RS names rarely sit on MA20
        min_score = float(_MIN_PATTERN_SCORE)
        dip_min_score = float(_MIN_PATTERN_SCORE) - 6  # 56 — bounce quality
        rs_min_score = float(_MIN_PATTERN_SCORE) - 4  # 58 — relative-strength hold
        eff_min_rr = float(min_rr)
        result_cap = int(max_results)
        size_mult = 1.0
        if open_policy == "defensive":
            min_score = _MIN_PATTERN_SCORE + (5 if f_score < 35 else 2)
            eff_min_rr = max(eff_min_rr, min_rr + 0.1, 1.4)
            result_cap = min(max(result_cap, 5), 8)
            size_mult = 0.55 if f_score < 30 else 0.70
        elif open_policy == "cautious":
            min_score = _MIN_PATTERN_SCORE  # 62 — do not raise just because index is mixed
            eff_min_rr = max(eff_min_rr, min_rr)
            result_cap = min(max(result_cap, 6), 8)
            size_mult = 0.85

        # Sizing follows forecast. Env exposure=0 (executor pause) must not
        # shrink the ticket below one affordable lot on typical A-share names.
        rec_exp = max(0.45, float(f_exposure or 0.7))
        if env_exposure > 0:
            rec_exp = min(1.0, 0.5 * rec_exp + 0.5 * max(env_exposure, 0.35))
        size_mult = max(0.40, min(1.0, size_mult * rec_exp))
        if prefer_dip and open_policy == "defensive":
            size_mult = min(size_mult, 0.55)
        buy_budget = min(budget * size_mult, cash)

        cache_key = (
            f"recq_{round(cash, 2)}_{round(equity, 2)}_{round(buy_budget, 2)}_"
            f"{round(pct, 4)}_{sizing_mode}_{result_cap}_{hold_days_hint}_{round(eff_min_rr, 2)}_"
            f"{env_state}_{open_policy}_{int(min_score)}_{int(f_score)}_{int(allow_dip)}_"
            f"{int(prefer_dip)}_{int(allow_rs)}_{round(env_exposure, 2)}_{days_below}"
        )
        if use_cache and not use_llm:
            cached = self._cache.get(cache_key)
            if cached and time.time() - cached["_ts"] < self._cache_ttl:
                return cached["data"]

        health = strategy_health_engine.get_health(env_state=env_state)

        max_px = (buy_budget / LOT_SIZE) if buy_budget > 0 else None
        # Weak tape: widen universe so oversold bounce names can appear
        uni_limit = min(120, int(universe_limit) + (30 if allow_dip else 0))
        symbols = self._build_universe(uni_limit, max_price=max_px, include_dip_pool=allow_dip)

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
        # Trend path: prefer relative strength; dip path allows brief lag vs tape
        rs_floor = -0.015 if open_policy == "open" else (-0.01 if not allow_dip else -0.02)

        for sym in symbols:
            scanned += 1
            try:
                item = self._evaluate_kline(
                    sym,
                    buy_budget,
                    cash,
                    hold_days_hint,
                    eff_min_rr,
                    min_score,
                    bench_ret_5=bench_ret_5,
                    quote=quote_map.get(sym),
                    rs_floor=rs_floor,
                    defensive=open_policy == "defensive",
                    allow_dip=allow_dip,
                    dip_min_score=dip_min_score,
                    allow_rs=allow_rs,
                    rs_min_score=rs_min_score,
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

        # Strategy health weighting + short-horizon forecast tilt
        forecast_tilt = 1.0
        if f_bias == "bull" and f_score >= 60:
            forecast_tilt = 1.05
        elif f_bias == "bear" or f_score < 35:
            forecast_tilt = 0.92

        for c in candidates:
            st = (c.get("suggested_strategy") or {}).get("type")
            w = strategy_health_engine.weight_for(health, st)
            status = strategy_health_engine.status_for(health, st)
            c["strategy_health_status"] = status
            c["strategy_health_weight"] = w
            base = float(c.get("score") or 0)
            # Dip / RS setups are meant for mixed tape — don't double-penalize with bear tilt
            tilt = 1.0 if (c.get("setup_type") or "") in ("dip_bounce", "rs_hold") else forecast_tilt
            c["adjusted_score"] = round(base * w * tilt, 2)
            hinfo = (health.get("strategies") or {}).get(st or "") or {}
            if hinfo.get("reason"):
                reasons = list(c.get("reasons") or [])
                reasons.insert(1, f"策略健康：{hinfo.get('name') or st}（{status}）")
                c["reasons"] = reasons[:6]
            if open_policy == "defensive":
                reasons = list(c.get("reasons") or [])
                if (c.get("setup_type") or "") == "dip_bounce":
                    reasons.insert(0, "弱市抄底路径：深跌后企稳反弹，仓位已按展望收紧")
                else:
                    reasons.insert(0, "弱市/过热：趋势回踩精选，提高门槛并收紧仓位")
                c["reasons"] = reasons[:6]
            elif (c.get("setup_type") or "") == "rs_hold":
                reasons = list(c.get("reasons") or [])
                reasons.insert(0, "弱市/轮动日：相对强势持有路径（不追涨停、不抄飞刀）")
                c["reasons"] = reasons[:6]
            elif prefer_dip and (c.get("setup_type") or "") == "dip_bounce":
                reasons = list(c.get("reasons") or [])
                tag = f"连续{days_below}日破位" if days_below >= 3 else "浅度回踩"
                reasons.insert(0, f"{tag}日优先抄底反弹，建议敞口约 {int(env_exposure * 100)}%")
                c["reasons"] = reasons[:6]
            elif f_score >= 60:
                reasons = list(c.get("reasons") or [])
                reasons.insert(0, f"短线市场展望偏多（预测分 {f_score:.0f}）")
                c["reasons"] = reasons[:6]

        kept = []
        dip_kept = 0
        trend_kept = 0
        rs_kept = 0
        for c in candidates:
            status = c.get("strategy_health_status")
            w = float(c.get("strategy_health_weight") or 0)
            setup = c.get("setup_type") or ""
            is_dip = setup == "dip_bounce"
            is_rs = setup == "rs_hold"
            cold_cut = 0.40 if (open_policy == "defensive" and not is_dip) else 0.30
            if status == "cold" and w < cold_cut:
                skipped["cold_strategy"] += 1
                continue
            kept.append(c)
            if is_dip:
                dip_kept += 1
            elif is_rs:
                rs_kept += 1
            else:
                trend_kept += 1

        kept.sort(
            key=lambda x: (
                -float(x.get("adjusted_score") or 0),
                -float(x.get("score") or 0),
            )
        )
        if result_cap >= 3 and (dip_kept or rs_kept):
            dips = [c for c in kept if (c.get("setup_type") or "") == "dip_bounce"]
            rss = [c for c in kept if (c.get("setup_type") or "") == "rs_hold"]
            trends = [
                c for c in kept
                if (c.get("setup_type") or "") not in ("dip_bounce", "rs_hold")
            ]
            dip_slots = 0
            if allow_dip and dips:
                dip_slots = min(len(dips), 2 if prefer_dip else 1)
            rs_slots = min(len(rss), max(2, result_cap // 3)) if rss else 0
            rest = max(0, result_cap - dip_slots - rs_slots)
            top = rss[:rs_slots] + dips[:dip_slots] + trends[:rest]
            # Fill leftover from remaining kept
            used = {id(x) for x in top}
            for c in kept:
                if len(top) >= result_cap:
                    break
                if id(c) not in used:
                    top.append(c)
            top.sort(
                key=lambda x: (
                    -float(x.get("adjusted_score") or 0),
                    -float(x.get("score") or 0),
                )
            )
            top = top[:result_cap]
        else:
            top = kept[:result_cap]
        for i, c in enumerate(top, 1):
            c["rank"] = i

        empty_reason = None
        if not top:
            empty_reason = self._explain_empty(skipped, buy_budget, cash, env, int(min_score))
            if skipped.get("cold_strategy"):
                empty_reason += "；匹配策略近期健康度偏低已过滤"
            if allow_dip:
                empty_reason += "；已启用弱市抄底路径仍无达标反弹结构"
            elif open_policy == "defensive":
                empty_reason += "；当前为防御模式（提高门槛后仍无达标标的）"

        policy_note = {
            "open": "短线市场展望偏多，按趋势回踩 + 相对强势结构筛选。",
            "cautious": (
                "指数中性/回踩时仍选股：相对强势持有 + 趋势回踩"
                + ("，并保留确认后的抄底反弹。" if allow_dip else "。")
                + "仓位按展望敞口，与执行器开仓锁解耦。"
            ),
            "defensive": (
                "展望偏弱时仍推荐有上涨空间的结构："
                "相对强势（不追涨停）+ 趋势回踩 + 深跌企稳抄底；"
                "收紧仓位，止损明确。"
            ),
        }.get(open_policy, "")

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
            "min_risk_reward": eff_min_rr,
            "min_pattern_score": int(min_score),
            "quality_policy": "rs_hold_plus_trend_pullback_plus_dip",
            "open_allowed": open_allowed,
            "open_policy": open_policy,
            "allow_dip": allow_dip,
            "prefer_dip": prefer_dip,
            "allow_rs": allow_rs,
            "size_mult": size_mult,
            "market_env": {
                "env_state": env.get("env_state"),
                "can_trade": env.get("can_trade"),
                "exposure_mult": env_exposure,
                "days_below_ma20": days_below,
                "shallow_pullback": shallow_pullback,
                "message": env.get("message"),
                "warnings": env.get("warnings") or [],
                "signals": env.get("signals") or [],
                "overheated": overheated,
            },
            "market_forecast": {
                "forecast_score": forecast.get("forecast_score"),
                "zone": forecast.get("zone"),
                "horizon_bias": forecast.get("horizon_bias"),
                "horizon_days": forecast.get("horizon_days"),
                "exposure_mult": forecast.get("exposure_mult"),
                "top_risk": forecast.get("top_risk"),
                "distribution_days_25": forecast.get("distribution_days_25"),
                "components": forecast.get("components") or {},
                "message": forecast.get("message"),
                "signals": forecast.get("signals") or [],
                "skills_basis": forecast.get("skills_basis") or [],
            },
            "strategy_health": health,
            "disclaimer": (
                "本推荐不构成投资建议，更不保证盈利。"
                f"{policy_note}"
                f"短线展望分 {f_score:.0f}/100（{forecast.get('message') or ''}）。"
                "流程：市场短线预测敞口 → 板块宇宙+当日强势股 → "
                "相对强势/趋势回踩/弱市抄底 → 涨停过滤 → 退出计划；宁缺毋滥。"
                "自动策略执行器仍可按大盘环境拒绝开仓，与本页人工精选解耦。"
            ),
            "scan_stats": {
                "universe": len(symbols),
                "scanned": scanned,
                "qualified": len(kept),
                "dip_candidates": dip_kept,
                "trend_candidates": trend_kept,
                "rs_candidates": rs_kept,
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
        if env.get("env_state") == "bear" or not env.get("can_trade"):
            parts.append(f"防御模式：结构分需≥{min_score}，且相对强弱不弱于大盘")
        elif env.get("overheated"):
            parts.append(f"过热防御：拒绝追高，结构分≥{min_score}")
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

    def _build_universe(
        self,
        limit: int,
        max_price: Optional[float] = None,
        include_dip_pool: bool = False,
    ) -> list:
        from app.engine.data_engine import data_engine

        symbols: list[str] = []
        seen: set[str] = set()

        def _norm(code: Optional[str]) -> Optional[str]:
            if not code:
                return None
            try:
                return data_engine.normalize_symbol(str(code))
            except Exception:
                return str(code).strip().upper() or None

        def _add(code: Optional[str]) -> None:
            code = _norm(code)
            if not code or code in seen:
                return
            bare = code.split(".")[0]
            # Collapse bare / .SH / .SZ duplicates from mixed sector+leader feeds
            if bare in seen:
                return
            seen.add(code)
            seen.add(bare)
            symbols.append(code)

        def _is_st_name(name: str) -> bool:
            return "ST" in (name or "").upper() or "退" in (name or "")

        # ── Hard sector gate (invest-a-share): prefer top bullish sectors ──
        sector_ok = False
        try:
            from app.engine.sector_engine import sector_engine

            ranking = sector_engine.rank_sectors() or []
            top_n = 10 if include_dip_pool else 8
            top = [s for s in ranking if not s.get("is_blacklisted")][:top_n]
            if not top:
                top = ranking[:top_n]
            # Weak market: also sample mid/laggard sectors for oversold bounce names
            dip_sectors = []
            if include_dip_pool and len(ranking) > top_n:
                mid = [s for s in ranking[top_n : top_n + 10] if not s.get("is_blacklisted")]
                # Prefer more negative change_pct for dip pool
                mid_sorted = sorted(
                    mid,
                    key=lambda s: float(
                        s.get("change_20d")
                        or s.get("change_pct")
                        or s.get("score")
                        or 0
                    ),
                )
                dip_sectors = mid_sorted[:6]

            codes = [s.get("sector_code") for s in top if s.get("sector_code")]
            dip_codes = [s.get("sector_code") for s in dip_sectors if s.get("sector_code")]
            if codes:
                sector_stocks = sector_engine.filter_stocks_by_sector(
                    codes, limit_per_sector=12 if include_dip_pool else 10
                )
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
            if dip_codes and len(symbols) < limit:
                dip_stocks = sector_engine.filter_stocks_by_sector(
                    dip_codes, limit_per_sector=8
                )
                for code in dip_stocks or []:
                    _add(code)
                    if len(symbols) >= limit:
                        break
                print(
                    f"[Recommend] universe +dip sectors={len(dip_codes)} "
                    f"total={len(symbols)}"
                )
            elif sector_ok:
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

        # Live leaders: reserve slots — sector fill often hits `limit` and would
        # otherwise hide today's RS names (the stocks with actual upside room).
        leader_budget = min(24, max(12, limit // 4))
        leaders = [_norm(c) for c in self._live_leader_codes(limit=leader_budget)]
        leaders = [c for c in leaders if c]
        if leaders:
            # Prefer leaders near the front so they survive [:limit]
            merged: list[str] = []
            seen2: set[str] = set()

            def _push(code: Optional[str]) -> None:
                code = _norm(code)
                if not code:
                    return
                bare = code.split(".")[0]
                if code in seen2 or bare in seen2:
                    return
                seen2.add(code)
                seen2.add(bare)
                merged.append(code)

            for code in leaders:
                _push(code)
            for code in symbols:
                _push(code)
                if len(merged) >= limit:
                    break
            symbols = merged[:limit]
            print(f"[Recommend] universe +live leaders={len(leaders)} total={len(symbols)}")

        return symbols[:limit]

    def _live_leader_codes(self, limit: int = 24) -> list:
        """Main/ChiNext/Star names with tradable gains (not limit-up, not BSE)."""
        from app.engine.data_engine import data_engine

        out: list[str] = []
        seen: set[str] = set()
        for board in ("main", "chinext", "star"):
            try:
                movers = data_engine.get_top_movers(12, board) or {}
            except Exception:
                continue
            for g in movers.get("gainers") or []:
                code = g.get("code") or ""
                if not code or code in seen:
                    continue
                if data_engine._market_board(code) == "bse":
                    continue
                name = str(g.get("name") or "")
                if "ST" in name.upper() or "退" in name:
                    continue
                chg = float(g.get("change_pct") or 0)
                # Skip untradable limit / empty noise; keep 1.2%~9% as "room today"
                cap = 19.5 if data_engine._market_board(code) in ("star", "chinext") else 9.5
                if chg < 1.2 or chg >= cap * 0.92:
                    continue
                seen.add(code)
                out.append(code)
                if len(out) >= limit:
                    return out
        return out

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
        rs_floor: float = -0.02,
        defensive: bool = False,
        allow_dip: bool = False,
        dip_min_score: float = 58.0,
        allow_rs: bool = True,
        rs_min_score: float = 58.0,
    ) -> Optional[dict]:
        """Score one symbol: trend pullback, RS hold, and/or weak-market dip bounce."""
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
        high_p = float(latest["high"] or close)
        low_p = float(latest["low"] or close)
        high_20 = float(latest["high_20"] or close)
        low_10 = float(latest["low_10"] or close)

        ret_5 = float(df["close"].iloc[-1] / df["close"].iloc[-6] - 1) if len(df) >= 6 else 0.0
        ret_10 = float(df["close"].iloc[-1] / df["close"].iloc[-11] - 1) if len(df) >= 11 else 0.0
        dist_ma20_signed = (close - ma20) / ma20 if ma20 > 0 else 0.0
        dist_ma20 = abs(dist_ma20_signed)
        drawdown = (high_20 - close) / high_20 if high_20 > 0 else 0.0
        bullish_candle = close > open_p
        vol_expand = vol > float(prev["volume"] or 0) * 1.3
        recent_vol = df["vol_ratio"].tail(6).iloc[:-1]
        had_shrink = bool((recent_vol < 0.7).any()) if len(recent_vol) else False
        low_prev = float(df["low"].iloc[-11:-1].min()) if len(df) >= 11 else low_10
        higher_low = low_10 >= low_prev * 0.995
        turnover = self._turnover(close, vol_ma if vol_ma > 0 else vol)
        liquid = turnover >= 20_000_000
        range_hl = max(high_p - low_p, 1e-9)
        close_loc = (close - low_p) / range_hl  # 1=close at high (hammer/strength)
        bounce_day = bullish_candle and close >= float(prev["close"]) * 0.998

        rs_5 = None
        if bench_ret_5 is not None:
            rs_5 = ret_5 - float(bench_ret_5)

        if not liquid:
            return None
        if ma20 <= 0 or ma60 <= 0:
            return None

        # ── Path A: trend pullback / reclaim (bull & weak tape) ──
        trend_ok = True
        if close < ma60 * 0.98:
            trend_ok = False
        if ma20_slope < 0 and close < ma20:
            trend_ok = False
        if drawdown < 0.005 and dist_ma20_signed > 0.06:
            trend_ok = False
        max_ext = 0.06 if defensive else 0.12
        if dist_ma20_signed > max_ext:
            trend_ok = False
        # Defensive trend path: prefer hold/reclaim MA20 (not free-fall chase)
        if defensive and close < ma20 * 0.995 and not (
            close >= ma20 and float(prev["close"]) < ma20 * 1.005
        ):
            # leave to dip path instead of hard reject whole symbol
            trend_ok = False
        if defensive and ma20_slope < 0 and close < ma20:
            trend_ok = False

        near_ma20 = dist_ma20 <= (0.015 if defensive else 0.02)
        trend_stack = ma5 >= ma10 >= ma20 and close >= ma20
        reclaim = close >= ma20 and float(prev["close"]) < ma20 * 1.005
        if trend_ok:
            if not (near_ma20 or reclaim):
                trend_ok = False
            elif not (had_shrink or (reclaim and vol_expand)):
                trend_ok = False
            elif rs_5 is not None and rs_5 < rs_floor:
                trend_ok = False

        # ── Path B: weak-market dip bounce (抄底反弹) ──
        dip_ok = False
        day_chg = (close / float(prev["close"]) - 1) if float(prev["close"]) > 0 else 0
        if allow_dip and not trend_ok:
            deep_enough = 0.05 <= drawdown <= 0.28
            washed = ret_5 <= -0.015 or close < ma20
            structure_ok = close >= ma60 * 0.90
            confirm = (bounce_day or close_loc >= 0.55) and (
                vol_expand or close_loc >= 0.55 or vol_ratio >= 1.0 or bullish_candle
            )
            not_crash = day_chg > -0.07
            dip_rs_ok = rs_5 is None or rs_5 >= -0.06
            dip_ok = bool(
                deep_enough and washed and structure_ok and confirm and not_crash and dip_rs_ok
            )

        # ── Path C: relative-strength hold (daily upside that is not a MA20 hug) ──
        rs_ok = False
        if allow_rs and not trend_ok and not dip_ok:
            hold_ma = close >= ma20 or (ma5 >= ma10 and close >= ma10 * 0.995)
            not_extended = dist_ma20_signed <= 0.08
            rs_lead = rs_5 is None or rs_5 >= 0.005
            day_ok = -0.02 <= day_chg < 0.092
            not_overhot = ret_5 <= 0.16 and drawdown >= 0.003
            vol_ok = vol_ratio >= 0.75 or bullish_candle
            mid_ok = close >= ma60 * 0.97
            rs_ok = bool(
                hold_ma and not_extended and rs_lead and day_ok and not_overhot and vol_ok and mid_ok
            )

        if not trend_ok and not dip_ok and not rs_ok:
            if rs_5 is not None and rs_5 < rs_floor and not allow_dip:
                return {"_skip": "weak_rs"}
            return None

        if trend_ok:
            setup_type = "trend_pullback"
        elif rs_ok:
            setup_type = "rs_hold"
        else:
            setup_type = "dip_bounce"

        # ── Pattern score ──
        score = 0.0
        shared: list[str] = []
        distinct: list[str] = []

        if setup_type == "rs_hold":
            score += 20
            distinct.append("相对强势：未贴MA20但仍站稳短均，短线仍有空间")
            if rs_5 is not None and rs_5 >= 0.02:
                score += 16
                distinct.append(f"5日相对强弱 +{rs_5 * 100:.1f}%")
            elif rs_5 is not None and rs_5 >= 0:
                score += 10
                distinct.append(f"5日相对强弱持平偏强（{rs_5 * 100:+.1f}%）")
            if close >= ma20:
                score += 12
                shared.append("价格站稳MA20")
            elif ma5 >= ma10:
                score += 8
                shared.append("MA5≥MA10 短线未坏")
            if ma20_slope >= 0:
                score += 8
                shared.append("MA20走平/向上")
            if close > ma60:
                score += 8
                shared.append("站稳MA60")
            if bullish_candle:
                score += 6
                shared.append("收阳线")
            if 0.01 <= drawdown <= 0.10:
                score += 6
                distinct.append(f"自高点回撤 {drawdown * 100:.1f}%（未高潮）")
            if vol_ratio >= 1.0:
                score += 6
            if liquid:
                score += 6
            if dist_ma20_signed > 0.06:
                score -= 8
                distinct.append("略偏离MA20，仓位宜轻")
        elif setup_type == "dip_bounce":
            score += 18
            distinct.append(f"弱市抄底：自20日高点回撤 {drawdown * 100:.1f}% 后企稳")
            if bounce_day:
                score += 12
                shared.append("出现止跌阳线/收复昨收")
            if vol_expand or vol_ratio >= 1.2:
                score += 12
                distinct.append("放量确认反弹意愿")
            elif close_loc >= 0.6:
                score += 8
                distinct.append("收盘靠近日内高点（多头占优）")
            if close >= ma60:
                score += 10
                shared.append("仍站稳MA60（中期未彻底破坏）")
            elif close >= ma60 * 0.95:
                score += 6
                shared.append("贴近MA60下方，反抽空间在")
            if close < ma20:
                score += 8
                distinct.append("价格仍在MA20下（典型抄底区，非追高）")
            if ret_5 <= -0.04:
                score += 6
                distinct.append(f"近5日超跌 {ret_5 * 100:.1f}%")
            if rs_5 is not None:
                if rs_5 >= 0:
                    score += 8
                    distinct.append(f"洗盘中相对抗跌（RS {rs_5 * 100:+.1f}%）")
                elif rs_5 >= -0.03:
                    score += 3
            if higher_low:
                score += 6
                shared.append("近端低点抬高")
            else:
                score += 2
            if liquid:
                score += 6
            # Cap extension above MA20 on dip path (shouldn't happen often)
            if dist_ma20_signed > 0.03:
                score -= 10
        else:
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
        if setup_type == "dip_bounce":
            need = dip_min_score
        elif setup_type == "rs_hold":
            need = rs_min_score
        else:
            need = min_score
        if score < need:
            return {"_skip": "low_score", "score": score}

        # ── Stops / targets ──
        if setup_type == "dip_bounce":
            structure_stop = min(low_10 * 0.992, close - 1.0 * atr, low_p * 0.995)
            structure_stop = max(structure_stop, close * 0.92)  # dip stop can be a bit wider
            risk = close - structure_stop
            if risk <= close * 0.01:
                return None
            # Target: reclaim MA20 or ATR bounce with RR
            reward_to_ma20 = max(ma20 - close, 0.0)
            reward = max(reward_to_ma20 * 0.9, 1.4 * atr, risk * max(1.3, min_rr - 0.2))
            eff_rr_need = max(1.3, min_rr - 0.2)
        elif setup_type == "rs_hold":
            structure_stop = min(ma10 * 0.995 if ma10 > 0 else close * 0.97, close - 1.1 * atr)
            structure_stop = max(structure_stop, close * 0.94)
            risk = close - structure_stop
            if risk <= close * 0.008:
                return None
            reward = max(1.5 * atr, risk * max(1.35, min_rr - 0.1))
            eff_rr_need = max(1.35, min_rr - 0.1)
        else:
            structure_stop = min(low_10 * 0.995, close - 1.2 * atr)
            structure_stop = max(structure_stop, close * 0.94)
            risk = close - structure_stop
            if risk <= close * 0.008:
                return None
            reward_to_high = max(high_20 - close, 0.0)
            reward = max(reward_to_high * 0.85, 1.6 * atr, risk * min_rr)
            eff_rr_need = min_rr

        rr = reward / risk
        if rr < eff_rr_need:
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
                "setup_type": setup_type,
            }
        )

        exit_plan = {
            "stop_loss": round(structure_stop, 3),
            "take_profit": round(target, 3),
            "take_profit_half": round(half_target, 3),
            "trail_ref_ma5": round(ma5, 3) if ma5 > 0 else None,
            "trail_atr": round(close - 1.5 * atr, 3),
            "time_stop_days": int(hold_days),
            "rules": (
                [
                    f"抄底仓：触及半仓目标 {half_target:.2f} 先减半锁定",
                    f"反抽至 MA20（{ma20:.2f}）附近可再评估加减",
                    f"硬止损 {structure_stop:.2f}，跌破当日/近低不摊薄",
                    f"持有约 {hold_days} 日未反弹则减仓复核",
                ]
                if setup_type == "dip_bounce"
                else [
                    f"触及半仓目标 {half_target:.2f} 可减半仓锁定利润",
                    f"剩余仓位跌破 MA5（{ma5:.2f}）或 ATR 跟踪位离场",
                    f"硬止损 {structure_stop:.2f}，不摊薄",
                    f"持有约 {hold_days} 个交易日未达标则减仓复核",
                ]
            ),
        }

        reasons = [
            f"匹配「{strategy['name']}」",
            f"盈亏比 {rr:.1f}:1（止损{structure_stop:.2f}/目标{target:.2f}）",
            *distinct,
            *shared,
        ]
        seen = set()
        reasons = [r for r in reasons if not (r in seen or seen.add(r))][:6]

        setup_label = {
            "dip_bounce": "抄底反弹",
            "rs_hold": "相对强势",
            "trend_pullback": "趋势回踩",
        }.get(setup_type, "趋势回踩")
        return {
            "symbol": symbol,
            "name": name,
            "price": round(close, 3),
            "setup_type": setup_type,
            "setup_label": setup_label,
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
                "setup_type": setup_type,
            },
            "suggested_strategy": strategy,
            "exit_plan": exit_plan,
            "reasons": reasons[:6],
            "action_plan": (
                f"【{setup_label}】日K结构分 {score}，匹配策略「{strategy['name']}」。"
                f"建议买入 {int(qty)} 股；止损 {structure_stop:.2f}；"
                f"半仓目标 {half_target:.2f} / 满仓目标 {target:.2f}；"
                f"计划持有约 {hold_days} 个交易日。"
                f"{'抄底仓严守止损、反抽减仓。' if setup_type == 'dip_bounce' else ('沿短均持有，跌破MA10减仓。' if setup_type == 'rs_hold' else '跌破 MA5 或硬止损离场，不摊薄成本。')}"
                f"{strategy.get('playbook', '')}"
            ),
        }

    @staticmethod
    def _match_strategy(pattern: dict) -> dict:
        """Map K-line pattern to the best-fit executable strategy.

        Scoring (not fixed if-else) so deep pullbacks → 龙回头,
        confirm-day bounce → 右侧入场, MA-stack continuation → 趋势跟踪,
        weak-market dip → 龙回头/右侧（抄底说明）.
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
        setup = pattern.get("setup_type") or "trend_pullback"

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

        if setup == "dip_bounce":
            dip = catalog["dragon_pullback"].copy()
            dip["name"] = "抄底反弹（龙回头框架）"
            dip["why"] = "弱市深跌后放量企稳，按龙回头/反弹框架轻仓试多"
            dip["playbook"] = (
                "操作要点：轻仓；硬止损看近低；反抽至MA20减仓；不摊薄、不追跌停反抽一日游。"
            )
            dip["match_score"] = 70.0
            return dip
        if setup == "rs_hold":
            rs = catalog["trend_following"].copy()
            rs["name"] = "相对强势（趋势跟踪框架）"
            rs["why"] = "指数一般时仍强于大盘、站稳短均，短线跟强不追涨停"
            rs["playbook"] = "操作要点：轻仓跟随；跌破MA10或硬止损离场；涨停板不追。"
            rs["match_score"] = 68.0
            return rs

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
            fallback["why"] = "未完善鲜明形态，默认按右侧确认框架谨慎操作"
            return fallback

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_type = scored[0][1]
        result = catalog[best_type].copy()
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
