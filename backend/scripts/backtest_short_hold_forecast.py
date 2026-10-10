"""Prove short-hold market-forecast filter vs legacy / unfiltered.

Compares three modes on the same symbols & window:
  1) unfiltered — always allow new entries
  2) legacy_ma20 — close>MA20 & MA20 rising & volume OK
  3) forecast40 — market_forecast_engine score >= 40

Usage (from backend/):
  python scripts/backtest_short_hold_forecast.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

# Ensure backend package root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.engine.backtest_engine import backtest_engine, BacktestEngine
from app.engine.market_forecast_engine import market_forecast_engine
from app.engine.market_env_engine import market_env_engine


def _legacy_ma20_dates(start: str, end: str) -> set:
    df = market_env_engine.get_avg_price_kline(500)
    if df is None or len(df) < 21:
        return set()
    df = df.copy()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma20_slope"] = df["ma20"].diff()
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["ok"] = (
        (df["close"] > df["ma20"])
        & (df["ma20_slope"] >= 0)
        & (df["volume"] >= df["vol_ma20"] * 0.7)
    )
    return {
        str(d)[:10]
        for d, b in zip(df["date"], df["ok"])
        if b and start <= str(d)[:10] <= end
    }


def _metrics(result: dict) -> dict:
    fr = result.get("filtered_result") or result
    if fr.get("status") != "completed":
        return {"status": fr.get("status"), "error": fr.get("error")}
    return {
        "status": "completed",
        "total_return_pct": fr.get("total_return_pct"),
        "max_drawdown_pct": fr.get("max_drawdown_pct"),
        "sharpe_ratio": fr.get("sharpe_ratio"),
        "win_rate": fr.get("win_rate"),
        "trade_count": fr.get("total_trades") or len(fr.get("trade_records") or []),
        "profit_factor": fr.get("profit_factor"),
    }


def main():
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    symbols = [
        "000001.SZ", "600519.SH", "000858.SZ", "601318.SH", "300750.SZ",
        "600036.SH", "000333.SZ", "002594.SZ", "601899.SH", "600276.SH",
    ]
    strategy = "ma"
    params = {"fast_period": 5, "slow_period": 20}

    live = market_forecast_engine.forecast(7)
    print("=== Live short-horizon forecast ===")
    print(
        json.dumps(
            {
                "forecast_score": live.get("forecast_score"),
                "zone": live.get("zone"),
                "horizon_bias": live.get("horizon_bias"),
                "exposure_mult": live.get("exposure_mult"),
                "top_risk": live.get("top_risk"),
                "message": live.get("message"),
                "skills_basis": live.get("skills_basis"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    series = market_forecast_engine.forecast_series(start, end)
    forecast_dates = set()
    if series is not None and len(series):
        forecast_dates = set(
            str(d)[:10]
            for d, s in zip(series["date"], series["forecast_score"])
            if float(s) >= 40
        )
    legacy_dates = _legacy_ma20_dates(start, end)

    print(f"\nWindow {start} → {end}")
    print(f"Forecast≥40 days: {len(forecast_dates)} | Legacy MA20 days: {len(legacy_dates)}")

    modes = [
        ("unfiltered", False, None),
        ("legacy_ma20", True, legacy_dates),
        ("forecast40", True, forecast_dates),
    ]

    summary = {"start": start, "end": end, "symbols": symbols, "strategy": strategy, "modes": {}}
    original_get = BacktestEngine._get_bullish_dates

    for name, enable_env, dates in modes:
        print(f"\n--- Running mode: {name} ---")
        if enable_env and dates is not None:
            def _make(ds):
                def _fn(self, start_date, end_date):
                    return {d for d in ds if start_date <= d <= end_date}
                return _fn
            BacktestEngine._get_bullish_dates = _make(dates)
        else:
            BacktestEngine._get_bullish_dates = original_get
        try:
            result = backtest_engine.run(
                strategy_type=strategy,
                parameters=params,
                symbols=symbols,
                start_date=start,
                end_date=end,
                initial_capital=1_000_000,
                enable_env_filter=enable_env,
                enable_sector_filter=False,
                comparison_mode=False,
            )
            m = _metrics(result)
        except Exception as e:
            m = {"status": "failed", "error": str(e)}
        summary["modes"][name] = m
        print(json.dumps(m, ensure_ascii=False, indent=2))

    BacktestEngine._get_bullish_dates = original_get

    u = summary["modes"].get("unfiltered") or {}
    f = summary["modes"].get("forecast40") or {}
    l = summary["modes"].get("legacy_ma20") or {}
    verdict = []
    if f.get("status") == "completed" and u.get("status") == "completed":
        try:
            if (f.get("sharpe_ratio") or 0) >= (u.get("sharpe_ratio") or 0):
                verdict.append("forecast40 Sharpe ≥ unfiltered")
            if abs(f.get("max_drawdown_pct") or 0) <= abs(u.get("max_drawdown_pct") or 0):
                verdict.append("forecast40 maxDD ≤ unfiltered")
            if (f.get("win_rate") or 0) >= (u.get("win_rate") or 0):
                verdict.append("forecast40 win_rate ≥ unfiltered")
        except Exception:
            pass
    if f.get("status") == "completed" and l.get("status") == "completed":
        try:
            if (f.get("sharpe_ratio") or 0) >= (l.get("sharpe_ratio") or 0) - 0.05:
                verdict.append("forecast40 Sharpe competitive vs legacy_ma20")
        except Exception:
            pass

    summary["verdict"] = verdict or ["see metrics table — data-dependent"]
    summary["live_forecast"] = {
        "forecast_score": live.get("forecast_score"),
        "zone": live.get("zone"),
        "message": live.get("message"),
    }

    out_dir = os.path.join(ROOT, "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "short_hold_forecast_backtest.json")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)
    print(f"\n=== Summary written to {out_path} ===")
    print("Verdict:", "; ".join(summary["verdict"]))
    return summary


if __name__ == "__main__":
    main()
