"""Rolling strategy health for capital-matched recommendations.

Evaluates recent buy-signal forward returns for each short-hold strategy
on a small liquid A-share sample. Used to weight / filter recommendations
so cold strategies are not treated as equally valid.

This is a lightweight rolling check — not a full portfolio backtest.
"""

from __future__ import annotations

import datetime
import time
from typing import Optional

import numpy as np
import pandas as pd

# Strategies used by recommend_engine._match_strategy
_RECOMMEND_STRATEGIES = ("dragon_pullback", "right_side_entry", "trend_following")

_STRATEGY_NAMES = {
    "dragon_pullback": "龙回头策略",
    "right_side_entry": "右侧入场策略",
    "trend_following": "趋势跟踪策略",
}


class StrategyHealthEngine:
    def __init__(self):
        self._cache: dict = {}
        self._cache_ttl = 45 * 60  # 45 minutes

    def get_health(
        self,
        *,
        env_state: str = "neutral",
        lookback_days: int = 90,
        sample_size: int = 12,
        force: bool = False,
    ) -> dict:
        """Return health snapshot for recommend strategies.

        Structure:
          {
            "generated_at": ...,
            "env_state": ...,
            "lookback_days": 90,
            "sample_size": N,
            "strategies": {
               "right_side_entry": {
                   "name", "status", "weight", "n_signals",
                   "win_rate", "avg_fwd_5d_pct", "reason"
               }, ...
            }
          }
        """
        cache_key = f"health_{env_state}_{lookback_days}_{sample_size}"
        if not force:
            hit = self._cache.get(cache_key)
            if hit and time.time() - hit["_ts"] < self._cache_ttl:
                return hit["data"]

        symbols = self._sample_symbols(sample_size)
        end = datetime.datetime.now().strftime("%Y-%m-%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=lookback_days + 40)).strftime(
            "%Y-%m-%d"
        )

        strategies: dict = {}
        for stype in _RECOMMEND_STRATEGIES:
            strategies[stype] = self._eval_strategy(stype, symbols, start, end, env_state)

        data = {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "env_state": env_state,
            "lookback_days": lookback_days,
            "sample_size": len(symbols),
            "symbols_used": symbols,
            "strategies": strategies,
            "disclaimer": (
                "策略健康度来自近期买入信号的向前收益统计，用于推荐加权，"
                "不是完整组合回测，不构成收益承诺。"
            ),
        }
        self._cache[cache_key] = {"_ts": time.time(), "data": data}
        return data

    def weight_for(self, health: dict, strategy_type: Optional[str]) -> float:
        if not strategy_type:
            return 0.7
        info = (health.get("strategies") or {}).get(strategy_type) or {}
        try:
            return float(info.get("weight", 0.7))
        except (TypeError, ValueError):
            return 0.7

    def status_for(self, health: dict, strategy_type: Optional[str]) -> str:
        info = (health.get("strategies") or {}).get(strategy_type or "") or {}
        return str(info.get("status") or "unknown")

    def _sample_symbols(self, n: int) -> list[str]:
        from app.engine.data_engine import data_engine

        try:
            data_engine.ensure_symbol_list()
        except Exception:
            pass

        pool = [s for s in (data_engine._symbols or []) if isinstance(s, dict)]
        # Prefer liquid large/mid names: skip ST
        cleaned = []
        for s in pool:
            name = str(s.get("name") or "")
            code = str(s.get("code") or "")
            if not code or "ST" in name.upper() or "退" in name:
                continue
            cleaned.append(code)

        if not cleaned:
            return ["600519.SH", "000001.SZ", "300750.SZ", "601318.SH", "000858.SZ"]

        # Spread across boards
        boards = {"main": [], "chinext": [], "star": []}
        for code in cleaned:
            bare = code.split(".")[0]
            if bare.startswith("30"):
                key = "chinext"
            elif bare.startswith("68"):
                key = "star"
            else:
                key = "main"
            if len(boards[key]) < max(2, n // 3 + 1):
                boards[key].append(code)

        out = boards["main"] + boards["chinext"] + boards["star"]
        # Fill from head of cleaned
        for code in cleaned:
            if len(out) >= n:
                break
            if code not in out:
                out.append(code)
        return out[:n]

    def _eval_strategy(
        self,
        strategy_type: str,
        symbols: list[str],
        start: str,
        end: str,
        env_state: str,
    ) -> dict:
        from app.engine.data_engine import data_engine
        from app.engine.strategy_engine import strategy_engine

        params = strategy_engine.get_default_params(strategy_type)
        fwd_rets: list[float] = []
        n_signals = 0

        for sym in symbols:
            try:
                df = data_engine.get_history_data(sym, start, end)
            except Exception:
                continue
            if df is None or len(df) < 80:
                continue
            df = df.copy()
            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close"])
            if len(df) < 80:
                continue

            try:
                sig = strategy_engine.calculate_signals(strategy_type, df, params)
            except Exception:
                continue
            if "buy_signal" not in sig.columns:
                continue

            closes = sig["close"].astype(float).values
            buys = sig["buy_signal"].fillna(False).astype(bool).values
            # Only evaluate recent window (last ~lookback trading bars)
            start_i = max(60, len(sig) - 70)
            for i in range(start_i, len(sig) - 5):
                if not buys[i]:
                    continue
                n_signals += 1
                entry = closes[i]
                if entry <= 0:
                    continue
                # No lookahead beyond available bars: 5-day forward close
                fwd = closes[i + 5]
                fwd_rets.append((fwd / entry) - 1.0)

        name = _STRATEGY_NAMES.get(strategy_type, strategy_type)
        if n_signals < 3 or not fwd_rets:
            # Soft default: scarce sample — cautious weight, do not hard-kill
            status = "scarce"
            weight = 0.55 if env_state == "bull" else 0.4
            reason = f"近期买入信号不足（{n_signals}次），健康度样本偏少"
            return {
                "type": strategy_type,
                "name": name,
                "status": status,
                "weight": weight,
                "n_signals": n_signals,
                "win_rate": None,
                "avg_fwd_5d_pct": None,
                "reason": reason,
            }

        arr = np.array(fwd_rets, dtype=float)
        win_rate = float((arr > 0).mean())
        avg_ret = float(arr.mean())
        avg_pct = round(avg_ret * 100, 2)
        win_pct = round(win_rate * 100, 1)

        # Status / weight (conservative; env modulates)
        if n_signals >= 8 and win_rate >= 0.48 and avg_ret > 0:
            status, weight = "healthy", 1.0
            reason = f"近期信号偏有效：胜率{win_pct}% / 5日均收益{avg_pct}%"
        elif n_signals >= 5 and win_rate >= 0.42 and avg_ret > -0.01:
            status, weight = "ok", 0.85
            reason = f"近期尚可：胜率{win_pct}% / 5日均收益{avg_pct}%"
        elif win_rate < 0.35 or avg_ret < -0.02:
            status, weight = "cold", 0.25
            reason = f"近期偏冷：胜率{win_pct}% / 5日均收益{avg_pct}% — 降权"
        else:
            status, weight = "weak", 0.55
            reason = f"近期偏弱：胜率{win_pct}% / 5日均收益{avg_pct}%"

        if env_state == "bear":
            weight *= 0.5
        elif env_state == "neutral":
            weight *= 0.75

        weight = round(max(0.15, min(1.0, weight)), 2)
        return {
            "type": strategy_type,
            "name": name,
            "status": status,
            "weight": weight,
            "n_signals": int(n_signals),
            "win_rate": win_pct,
            "avg_fwd_5d_pct": avg_pct,
            "reason": reason,
        }


strategy_health_engine = StrategyHealthEngine()
