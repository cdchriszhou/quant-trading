"""Backtest Engine: Multi-layer strategy backtesting with pre-filtering.

Implements Core 4 from req.txt:
  1. No more brute-force full-market scanning
  2. Layer 1 — Market environment filter (only trade on bullish days)
  3. Layer 2 — Sector screening (only trade stocks in top-N sectors)
  4. Layer 3 — Run trading rules
  5. Comparison: filtered vs unfiltered results side-by-side
  6. Parameter optimization: auto-test MA & volume combos

Hard rules:
  - No future-function leakage (signals computed on t-day close, traded on t+1)
  - No mid-session strategy changes
  - Fixed stop-loss and position sizing
"""

import math
import itertools
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from app.engine.data_engine import data_engine
from app.engine.strategy_engine import strategy_engine


class BacktestEngine:
    """Backtesting engine with 2-layer pre-filtering, comparison mode, and param optimization."""

    def run(self, strategy_type: str, parameters: dict, symbols: list,
            start_date: str, end_date: str, initial_capital: float = 100000.0,
            commission_rate: float = 0.00025, slippage: float = 0.001,
            enable_env_filter: bool = True,
            enable_sector_filter: bool = True,
            comparison_mode: bool = True) -> dict:
        """Run backtest with optional pre-filtering layers.

        When comparison_mode=True, runs twice — with and without filters —
        and returns a side-by-side comparison.
        """

        if not symbols:
            symbols = ["000001.SZ"]

        # ── Run with filters ──
        filtered_df, filter_info = self._apply_pre_filters(
            symbols, start_date, end_date, enable_env_filter, enable_sector_filter
        )

        filtered_result = self._run_single(
            strategy_type, parameters, filtered_df, symbols,
            start_date, end_date, initial_capital, commission_rate, slippage,
        )
        filtered_result["filter_info"] = filter_info

        result = {
            "status": "completed",
            "strategy_type": strategy_type,
            "parameters": parameters,
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "filtered_result": filtered_result,
        }

        # ── Run without filters (comparison) ──
        if comparison_mode and (enable_env_filter or enable_sector_filter):
            unfiltered_df, _ = self._apply_pre_filters(
                symbols, start_date, end_date,
                enable_env_filter=False, enable_sector_filter=False,
            )
            unfiltered_result = self._run_single(
                strategy_type, parameters, unfiltered_df, symbols,
                start_date, end_date, initial_capital, commission_rate, slippage,
            )
            result["unfiltered_result"] = unfiltered_result
            result["comparison"] = self._compute_comparison(filtered_result, unfiltered_result)

        return result

    # ── Pre-filtering logic ────────────────────────────────────────

    def _apply_pre_filters(self, symbols: list, start_date: str, end_date: str,
                           enable_env: bool, enable_sector: bool) -> tuple:
        """Apply environment and sector pre-filters.

        Returns (filtered_df_dict, filter_info).
        filtered_df_dict: {symbol: DataFrame with env_filter column added}
        """
        filter_info = {
            "env_filter_enabled": enable_env,
            "sector_filter_enabled": enable_sector,
            "bullish_days": 0,
            "total_days": 0,
            "sectors_used": [],
            "stocks_filtered_out": 0,
        }

        df_dict = {}
        for sym in symbols:
            df = data_engine.get_history_data(sym, start_date, end_date)
            if df is not None and not df.empty:
                df_dict[sym] = df

        if not df_dict:
            return df_dict, filter_info

        total_before = sum(len(df) for df in df_dict.values())
        filter_info["total_days"] = max(len(df) for df in df_dict.values()) if df_dict else 0

        # Layer 1: Market environment filter
        if enable_env:
            env_bullish_dates = self._get_bullish_dates(start_date, end_date)
            filter_info["bullish_days"] = len(env_bullish_dates)
            for sym, df in df_dict.items():
                df["env_permitted"] = df["date"].isin(env_bullish_dates).astype(int)
                # Only keep rows on bullish days (but keep all for signal calc context)
        else:
            for sym, df in df_dict.items():
                df["env_permitted"] = 1

        # Layer 2: Sector filter
        if enable_sector:
            top_sector_stocks = self._get_top_sector_stocks()
            filter_info["sectors_used"] = top_sector_stocks.get("sectors", [])
            allowed_set = set(top_sector_stocks.get("stocks", []))
            if allowed_set:
                for sym, df in df_dict.items():
                    df["sector_permitted"] = 1 if sym in allowed_set else 0
                # Count stocks filtered out
                filter_info["stocks_filtered_out"] = sum(
                    1 for s in symbols if s not in allowed_set
                )
            else:
                for sym, df in df_dict.items():
                    df["sector_permitted"] = 1
        else:
            for sym, df in df_dict.items():
                df["sector_permitted"] = 1

        total_after = sum(len(df) for df in df_dict.values())
        filter_info["data_reduction_pct"] = round(
            (1 - total_after / total_before) * 100, 2
        ) if total_before > 0 else 0

        return df_dict, filter_info

    def _get_bullish_dates(self, start_date: str, end_date: str) -> set:
        """Compute which trading days are 'bullish' within a date range.

        Uses the MarketEnvEngine to simulate historical environment checks.
        Since we can't check live historical env, we use a simplified approach:
        look at the average price index trend to determine bullish periods.
        """
        from app.engine.market_env_engine import market_env_engine

        df = market_env_engine.get_avg_price_kline(500)
        if df is None or len(df) < 21:
            return set()

        ma_period = 20
        df["ma20"] = df["close"].rolling(window=ma_period).mean()
        df["ma20_slope"] = df["ma20"].diff()
        df["vol_ma20"] = df["volume"].rolling(window=20).mean()
        min_vol_ratio = 0.7

        # Mark bullish days
        df["bullish"] = (
            (df["close"] > df["ma20"]) &
            (df["ma20_slope"] >= 0) &
            (df["volume"] >= df["vol_ma20"] * min_vol_ratio)
        )

        bullish_dates = set(
            d for d, b in zip(df["date"], df["bullish"])
            if b and start_date <= str(d)[:10] <= end_date
        )
        return bullish_dates

    @staticmethod
    def _get_top_sector_stocks() -> dict:
        """Get all stock symbols belonging to top-N bullish sectors."""
        try:
            from app.engine.sector_engine import sector_engine
            top_sectors = sector_engine.get_top_sectors(10)
            sector_codes = [s["sector_code"] for s in top_sectors]
            stocks = sector_engine.filter_stocks_by_sector(sector_codes, limit_per_sector=50)
            return {
                "sectors": [s["sector_name"] for s in top_sectors],
                "stocks": stocks,
            }
        except Exception:
            return {"sectors": [], "stocks": []}

    # ── Single backtest run ────────────────────────────────────────

    def _run_single(self, strategy_type: str, parameters: dict,
                    df_dict: dict, symbols: list,
                    start_date: str, end_date: str,
                    initial_capital: float, commission_rate: float, slippage: float) -> dict:
        """Run a single backtest pass on the (potentially pre-filtered) data."""

        if not df_dict:
            return {"status": "failed", "error": "No data available after filtering"}

        # Multi-symbol: loop through each and combine results
        all_equity_curves = []
        all_trades = []
        combined_stats = None

        for sym, df in df_dict.items():
            if df is None or df.empty:
                continue

            # Filter to date range
            mask = (df["date"] >= start_date) & (df["date"] <= end_date)
            df_range = df[mask].copy()
            if df_range.empty:
                continue

            # Calculate signals
            try:
                signal_df = strategy_engine.calculate_signals(strategy_type, df_range, parameters)
            except ValueError:
                signal_df = df_range
                signal_df["buy_signal"] = False
                signal_df["sell_signal"] = False
                signal_df["signal_strength"] = 0.0

            # Apply env filter: only allow buys on permitted days
            if "env_permitted" in signal_df.columns:
                signal_df["buy_signal"] = signal_df["buy_signal"] & (signal_df["env_permitted"] == 1)

            # Apply sector filter: only trade permitted stocks
            if "sector_permitted" in signal_df.columns:
                signal_df["buy_signal"] = signal_df["buy_signal"] & (signal_df["sector_permitted"] == 1)

            # Simulate trading
            equity_curve, trades, stats = self._simulate(
                signal_df, initial_capital / max(len(df_dict), 1),
                commission_rate, slippage,
            )
            all_equity_curves.append(equity_curve)
            all_trades.extend(trades)

            if combined_stats is None:
                combined_stats = stats.copy()
            else:
                # Merge stats
                combined_stats["final_capital"] += stats["final_capital"]
                combined_stats["total_trades"] += stats["total_trades"]
                combined_stats["winning_trades"] += stats["winning_trades"]
                combined_stats["losing_trades"] += stats["losing_trades"]

        if combined_stats is None:
            return {"status": "failed", "error": "No trades simulated"}

        # Recompute derived stats
        final_cap = combined_stats["final_capital"]
        total_return = final_cap - initial_capital
        total_return_pct = (final_cap / initial_capital - 1) * 100 if initial_capital > 0 else 0

        # Merge equity curves
        merged_equity = self._merge_equity_curves(all_equity_curves)
        max_dd, max_dd_pct = self._calc_max_drawdown(merged_equity)
        sharpe = self._calc_sharpe(merged_equity)
        win_rate = (
            combined_stats["winning_trades"] / combined_stats["total_trades"] * 100
            if combined_stats["total_trades"] > 0 else 0
        )
        profit_factor = self._calc_profit_factor(all_trades)
        consecutive_losses = self._calc_consecutive_losses(all_trades)

        # Annualized return
        days = len(merged_equity) if merged_equity else 1
        years = days / 252
        annual_return = ((final_cap / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        return {
            "status": "completed",
            "final_capital": round(final_cap, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return_pct, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "total_trades": combined_stats["total_trades"],
            "winning_trades": combined_stats["winning_trades"],
            "losing_trades": combined_stats["losing_trades"],
            "consecutive_losses": consecutive_losses,
            "equity_curve": merged_equity,
            "trade_records": all_trades,
        }

    def _simulate(self, df: pd.DataFrame, initial_capital: float,
                  commission_rate: float, slippage: float) -> tuple:
        """Simulate trading on signal data. Uses t+1 execution to avoid future leakage."""

        capital = initial_capital
        position = 0.0
        avg_entry_price = 0.0
        trades = []
        equity_curve = []

        prev_buy_signal = False
        prev_sell_signal = False
        prev_price = 0.0

        for idx, row in df.iterrows():
            price = row["close"]
            buy_signal = row.get("buy_signal", False)
            sell_signal = row.get("sell_signal", False)
            date_str = str(row.get("date", ""))

            # Record equity at current price
            equity = capital + position * price
            equity_curve.append({"date": date_str, "equity": round(equity, 2)})

            # Execute signals at t+1 price (avoid future leakage)
            # Use previous signal, current price
            if prev_buy_signal and capital > 0:
                buy_amount = capital * 0.95
                shares = buy_amount / (price * (1 + slippage))
                cost = shares * price * (1 + slippage)
                commission = max(cost * commission_rate, 5.0)
                total_cost = cost + commission
                if total_cost <= capital:
                    total_cost_basis = position * avg_entry_price + cost
                    position += shares
                    capital -= total_cost
                    avg_entry_price = total_cost_basis / position if position > 0 else 0
                    trades.append({
                        "date": date_str,
                        "side": "buy",
                        "price": round(price, 2),
                        "quantity": round(shares, 2),
                        "amount": round(total_cost, 2),
                        "commission": round(commission, 2),
                        "pnl": 0,
                    })

            elif prev_sell_signal and position > 0:
                sell_value = position * price * (1 - slippage)
                commission = max(sell_value * commission_rate, 5.0)
                total_received = sell_value - commission
                pnl = total_received - (position * avg_entry_price)
                trades.append({
                    "date": date_str,
                    "side": "sell",
                    "price": round(price, 2),
                    "quantity": round(position, 2),
                    "amount": round(sell_value, 2),
                    "commission": round(commission, 2),
                    "pnl": round(pnl, 2),
                })
                capital += total_received
                position = 0.0
                avg_entry_price = 0.0

            prev_buy_signal = buy_signal
            prev_sell_signal = sell_signal
            prev_price = price

        # Final equity (liquidate remaining position at last price)
        final_price = df["close"].iloc[-1] if len(df) > 0 else 0
        final_capital = capital + position * final_price

        # Stats
        winning_trades = len([t for t in trades if t["side"] == "sell" and t.get("pnl", 0) > 0])
        losing_trades = len([t for t in trades if t["side"] == "sell" and t.get("pnl", 0) <= 0])
        total_sells = winning_trades + losing_trades

        stats = {
            "final_capital": final_capital,
            "total_trades": len(trades),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
        }

        return equity_curve, trades, stats

    # ── Statistics helpers ──────────────────────────────────────────

    @staticmethod
    def _merge_equity_curves(curves: list) -> list:
        """Merge multiple equity curves by date (sum equity at each date)."""
        if not curves:
            return []
        if len(curves) == 1:
            return curves[0]

        # Build a date → total_equity map
        date_equity: dict = {}
        for curve in curves:
            for entry in curve:
                d = entry["date"]
                eq = entry.get("equity", 0)
                date_equity[d] = date_equity.get(d, 0) + eq

        # Sort by date
        merged = [{"date": d, "equity": round(eq, 2)}
                   for d, eq in sorted(date_equity.items())]
        return merged

    @staticmethod
    def _calc_max_drawdown(equity_curve: list) -> tuple:
        """Calculate max drawdown in absolute and percentage terms."""
        if not equity_curve:
            return 0, 0
        values = [e["equity"] for e in equity_curve]
        peak = values[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = peak - v
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        return max_dd, max_dd_pct

    @staticmethod
    def _calc_sharpe(equity_curve: list) -> float:
        """Calculate Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        values = [e["equity"] for e in equity_curve]
        daily_returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values)) if values[i-1] > 0]
        if not daily_returns:
            return 0.0
        avg = np.mean(daily_returns)
        std = np.std(daily_returns)
        return (avg / std * math.sqrt(252)) if std > 0 else 0.0

    @staticmethod
    def _calc_profit_factor(trades: list) -> float:
        """Profit factor = gross profit / gross loss."""
        gross_profit = sum(t.get("pnl", 0) for t in trades if t["side"] == "sell" and t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t["side"] == "sell" and t.get("pnl", 0) < 0))
        return gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

    @staticmethod
    def _calc_consecutive_losses(trades: list) -> int:
        """Calculate maximum consecutive losing trades."""
        max_consecutive = 0
        current = 0
        for t in trades:
            if t["side"] == "sell":
                if t.get("pnl", 0) <= 0:
                    current += 1
                    max_consecutive = max(max_consecutive, current)
                else:
                    current = 0
        return max_consecutive

    @staticmethod
    def _compute_comparison(filtered: dict, unfiltered: dict) -> dict:
        """Compute improvement metrics between filtered and unfiltered results."""
        f_ret = filtered.get("total_return_pct", 0) or 0
        u_ret = unfiltered.get("total_return_pct", 0) or 0
        f_dd = filtered.get("max_drawdown_pct", 0) or 0
        u_dd = unfiltered.get("max_drawdown_pct", 0) or 0
        f_wr = filtered.get("win_rate", 0) or 0
        u_wr = unfiltered.get("win_rate", 0) or 0
        f_tr = filtered.get("total_trades", 0) or 0
        u_tr = unfiltered.get("total_trades", 0) or 0
        f_cl = filtered.get("consecutive_losses", 0) or 0
        u_cl = unfiltered.get("consecutive_losses", 0) or 0

        return {
            "return_improvement_pct": round(f_ret - u_ret, 2),
            "drawdown_reduction_pct": round(u_dd - f_dd, 2),
            "win_rate_improvement_pct": round(f_wr - u_wr, 2),
            "trade_count_reduction_pct": round((1 - f_tr / u_tr) * 100, 2) if u_tr > 0 else 0,
            "consecutive_losses_filtered": f_cl,
            "consecutive_losses_unfiltered": u_cl,
            "summary": (
                f"增加大盘+板块筛选后：收益率变化 {f_ret - u_ret:+.1f}%，"
                f"最大回撤变化 {u_dd - f_dd:+.1f}%（负数=改善），"
                f"胜率变化 {f_wr - u_wr:+.1f}%"
            ),
        }

    # ── Parameter optimization ──────────────────────────────────────

    def optimize(self, strategy_type: str, base_parameters: dict, symbols: list,
                 start_date: str, end_date: str,
                 initial_capital: float = 100000.0,
                 enable_env_filter: bool = True,
                 enable_sector_filter: bool = True) -> dict:
        """Auto-test parameter combinations to find the most stable set.

        Tests variations of:
          - MA periods (short 3-10, medium 15-30)
          - Volume contraction ratios (0.3-0.7)
          - Volume expansion ratios (1.2-2.0)
          - Stop-loss percentages (3-10%)
        """

        param_grid = {
            "ma_short": [3, 5, 7, 10],
            "ma_medium": [15, 20, 25, 30],
            "pullback_near_ma_pct": [1.0, 2.0, 3.0],
            "vol_contraction_ratio": [0.3, 0.5, 0.7],
            "vol_expansion_ratio": [1.2, 1.5, 2.0],
            "stop_loss_ma_break_pct": [1.0, 2.0, 3.0],
            "hard_stop_pct": [5.0, 7.0, 10.0],
        }

        # Build parameter combinations (limit to ~50 to avoid explosion)
        keys = list(param_grid.keys())
        combinations = []
        # Take a representative sample rather than full grid
        for combo in itertools.product(
            param_grid["ma_short"][:2],
            param_grid["ma_medium"][:2],
            param_grid["pullback_near_ma_pct"][:2],
            param_grid["vol_contraction_ratio"][:2],
            param_grid["vol_expansion_ratio"][:2],
            param_grid["stop_loss_ma_break_pct"][:2],
        ):
            params = base_parameters.copy()
            params.update({
                "ma_short": combo[0],
                "ma_medium": combo[1],
                "pullback_near_ma_pct": combo[2],
                "vol_contraction_ratio": combo[3],
                "vol_expansion_ratio": combo[4],
                "stop_loss_ma_break_pct": combo[5],
                "ma_long": 60,
                "hard_stop_pct": 7.0,
            })
            combinations.append(params)

        # Test each combination
        results = []
        best_score = -float("inf")
        best_params = None

        for i, params in enumerate(combinations[:48]):  # Cap at 48 runs
            result = self.run(
                strategy_type=strategy_type,
                parameters=params,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                enable_env_filter=enable_env_filter,
                enable_sector_filter=enable_sector_filter,
                comparison_mode=False,
            )
            filtered = result.get("filtered_result", {})
            if filtered.get("status") != "completed":
                continue

            # Composite score: weight return, penalize drawdown
            ret = filtered.get("total_return_pct", 0) or 0
            dd = filtered.get("max_drawdown_pct", 100) or 100
            wr = filtered.get("win_rate", 0) or 0
            cl = filtered.get("consecutive_losses", 99) or 99
            score = ret * 1.0 - dd * 0.5 + wr * 0.3 - cl * 2.0

            results.append({
                "params": params,
                "return_pct": ret,
                "max_drawdown_pct": dd,
                "win_rate": wr,
                "consecutive_losses": cl,
                "score": round(score, 2),
            })

            if score > best_score:
                best_score = score
                best_params = params

        results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "best_params": best_params,
            "best_score": round(best_score, 2),
            "total_tested": len(results),
            "top_results": results[:10],
        }


backtest_engine = BacktestEngine()
