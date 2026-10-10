---
name: ashare-market-forecast
description: >
  A-share short-horizon (5–10d) market outlook for short-hold recommendations.
  Synthesizes installed skills: uptrend-analyzer, market-top-detector,
  market-breadth-analyzer, market-environment-analysis, alpha-signal.
  Triggers: "市场展望", "短线预测", "forecast market", "ashare-market-forecast"
---

# ashare-market-forecast — A股短线市场展望

## Installed skill basis (from GitHub)

| Skill | Source | What we reuse |
|-------|--------|----------------|
| uptrend-analyzer | mphinance/alpha-skills | 0–100 health → exposure bands |
| market-top-detector | mphinance/alpha-skills | Distribution days / top risk (2–8w) |
| market-breadth-analyzer | mphinance/alpha-skills | Participation / breadth health |
| market-environment-analysis | mphinance/alpha-skills | Risk-on/off + 1–5d outlook |
| alpha-signal | VernonOY/alpha-skills | Regime-aware sizing for target book |
| alpha-backtest | VernonOY/alpha-skills | Gate + IS/OOS style validation |

Project copies live under `.agents/skills/<name>/SKILL.md`.

## Engine

Implementation: `backend/app/engine/market_forecast_engine.py`

- `forecast()` — live 0–100 score + `exposure_mult` + `horizon_bias` + `top_risk`
- `forecast_series(start, end)` — no look-ahead series for backtests

## Wire-up

1. **Short-hold recommend** (`recommend_engine`): blend env + forecast → open_policy / size_mult / score tilt; never blank the list solely because executor `can_trade=False`.
2. **Backtest** (`backtest_engine._get_bullish_dates`): prefer forecast_score ≥ 40 vs legacy MA20-only gate.
3. **Proof script**: `backend/scripts/backtest_short_hold_forecast.py`

## Output contract

When discussing market outlook for short-hold:

1. Report `forecast_score`, zone, exposure_mult, top_risk, distribution_days_25
2. Separate **executor gate** (`can_trade`) from **recommend policy** (defensive/cautious/open)
3. Prefer risk-controlled picks in weak/overheated tape; do not refuse to recommend
4. **Shallow pullback ≠ bear**: price within ~2.5% under MA20 + MA20 rising + MA stack intact
   → label 回踩整理 / allow cautious opens & dip picks (uptrend-analyzer Reduced exposure),
   never "空头市场 — 禁止开仓" from a single weak breadth day alone
