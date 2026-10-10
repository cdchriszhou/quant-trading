"""Audit recommend gates vs live gainers / env (no look-ahead)."""
from __future__ import annotations

import json
import sys
from collections import Counter

sys.path.insert(0, ".")

from app.engine.market_env_engine import market_env_engine
from app.engine.market_forecast_engine import market_forecast_engine
from app.engine.data_engine import data_engine
from app.engine.recommend_engine import recommend_engine, _MIN_PATTERN_SCORE


def main():
    env = market_env_engine.check_environment()
    fc = market_forecast_engine.forecast(horizon_days=5)
    print("=== ENV ===")
    print({
        "env_state": env.get("env_state"),
        "can_trade": env.get("can_trade"),
        "exposure_mult": env.get("exposure_mult"),
        "days_below": env.get("days_below_ma20"),
        "message": env.get("message"),
        "overheated": env.get("overheated"),
        "shallow": (env.get("checklist") or {}).get("shallow_pullback"),
    })
    print("=== FORECAST ===")
    print({
        "score": fc.get("forecast_score"),
        "zone": fc.get("zone"),
        "bias": fc.get("horizon_bias"),
        "exposure": fc.get("exposure_mult"),
        "top_risk": fc.get("top_risk"),
        "message": fc.get("message"),
    })

    rec = recommend_engine.recommend(
        cash=100000,
        total_equity=100000,
        max_position_pct=0.25,
        max_results=8,
        use_cache=False,
        universe_limit=80,
    )
    print("=== RECOMMEND META ===")
    meta_keys = [
        "open_policy", "open_allowed", "allow_dip", "prefer_dip", "size_mult",
        "min_pattern_score", "budget_per_name", "empty_reason",
    ]
    print({k: rec.get(k) for k in meta_keys})
    print("scan_stats", rec.get("scan_stats"))
    items = rec.get("items") or rec.get("recommendations") or rec.get("data") or []
    if isinstance(rec.get("recommendations"), list):
        items = rec["recommendations"]
    elif isinstance(rec.get("candidates"), list) and not items:
        items = rec["candidates"]
    # common key
    for k in ("items", "list", "picks", "stocks"):
        if isinstance(rec.get(k), list) and rec[k] and isinstance(rec[k][0], dict) and rec[k][0].get("symbol"):
            items = rec[k]
            break
    print("n_items", len(items) if isinstance(items, list) else type(items))
    if isinstance(items, list):
        for it in items[:8]:
            print(" ", it.get("symbol"), it.get("name"), it.get("setup_type"), it.get("score"), it.get("reasons", [""])[0][:40])

    # Why today's gainers would fail current paths
    movers = data_engine.get_top_movers(15, "all") or {}
    gainers = movers.get("gainers") or []
    print("=== GAINERS SAMPLE ===", len(gainers))
    skip = Counter()
    for g in gainers[:15]:
        code = g.get("code") or g.get("symbol")
        if not code:
            continue
        from app.engine.data_engine import DataEngine
        sym = DataEngine.normalize_symbol(str(code))
        item = recommend_engine._evaluate_kline(
            sym,
            budget=25000,
            cash=100000,
            hold_days=7,
            min_rr=1.5,
            min_score=float(_MIN_PATTERN_SCORE) + 6,
            bench_ret_5=recommend_engine._benchmark_ret_5d(),
            quote=g if "current_price" in g else None,
            rs_floor=-0.02,
            defensive=True,
            allow_dip=True,
            dip_min_score=58,
        )
        chg = g.get("change_pct") or g.get("pct")
        name = g.get("name") or ""
        if item is None:
            skip["weak_setup"] += 1
            print(f"  {sym} {name} chg={chg} -> weak_setup")
        elif item.get("_skip"):
            skip[item["_skip"]] += 1
            print(f"  {sym} {name} chg={chg} -> skip {item['_skip']} score={item.get('score')}")
        else:
            skip["PASS"] += 1
            print(f"  {sym} {name} chg={chg} -> PASS {item.get('setup_type')} {item.get('score')}")
    print("gainer skip", dict(skip))


if __name__ == "__main__":
    main()
