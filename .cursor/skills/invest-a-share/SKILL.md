---
name: invest-a-share
description: >-
  A-share oriented investment analysis frameworks adapted from InvestSkill-style
  prompts: technical analysis, sector rotation, risk checklist for short-hold
  recommendations. Use when refining recommend_engine scoring, writing stock
  reports, or reviewing entry/exit rules for China equities.
---

# A-Share Invest Analysis (InvestSkill-adapted)

InvestSkill's official Cursor install skipped skills missing `name` frontmatter.
This project skill keeps the useful checklists for **A-share short-hold** work.

## When to use

- Improving `recommend_engine` structure scores / RR / stops
- Writing per-stock recommendation rationale
- Reviewing strategy entry/exit consistency with live executor

## Technical checklist (short-hold)

### A. Trend pullback (bull / normal tape)
1. **Trend**: MA5 > MA10 > MA20, MA20 slope ≥ 0
2. **Pullback**: price near MA20 (within ~2%), not broken
3. **Volume**: contraction on pullback, expansion on reclaim/breakout
4. **Higher lows**: recent swing low above prior swing low
5. **Risk**: stop under structure or ATR multiple; target ≥ min RR × risk

### B. Dip bounce (weak tape — 抄底反弹)
1. **Washout**: 7–28% off 20d high, or 5d return ≤ -2% / below MA20
2. **Structure**: still near MA60 (not >10% under) — medium-term not destroyed
3. **Confirm**: bounce day (close ≥ prior close) + volume expand or close near day high
4. **Risk**: stop under recent swing low; light size; take profit toward MA20 reclaim
5. Never chase limit-down one-day spikes without confirmation

### Shared hard filters
Skip ST/*ST, suspended, limit-up/limit-down untradable, insufficient liquidity.

## Sector lens

- Prefer names in top bullish sectors (multi-MA alignment)
- Avoid blacklisted / extreme speculative plates for capital-matched sizing

## Output contract

For each candidate report: score, entry, stop, target, RR, matched strategy type, and explicit "why skipped" when rejected.
