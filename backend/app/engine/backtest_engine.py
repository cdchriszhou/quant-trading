"""Backtest Engine: Strategy backtesting with historical data."""

import math
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

from app.engine.data_engine import data_engine
from app.engine.strategy_engine import strategy_engine


class BacktestEngine:
    """Backtesting engine that runs strategies on historical data."""

    def run(self, strategy_type: str, parameters: dict, symbols: list,
            start_date: str, end_date: str, initial_capital: float = 100000.0,
            commission_rate: float = 0.00025, slippage: float = 0.001) -> dict:
        """Run a backtest for the given strategy and return results."""

        if not symbols:
            symbols = ["000001.SZ"]

        # Get data for the first symbol (multi-symbol support simplified)
        df = data_engine.get_history_data(symbols[0], start_date, end_date)
        if df.empty:
            return {"status": "failed", "error": "No data available"}

        # Calculate signals
        df = strategy_engine.calculate_signals(strategy_type, df, parameters)
        if df.empty:
            return {"status": "failed", "error": "Signal calculation failed"}

        # Run simulation
        equity_curve, trades, stats = self._simulate(
            df, initial_capital, commission_rate, slippage
        )

        return {
            "status": "completed",
            "strategy_type": strategy_type,
            "parameters": parameters,
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "final_capital": round(stats["final_capital"], 2),
            "total_return": round(stats["total_return"], 2),
            "total_return_pct": round(stats["total_return_pct"], 2),
            "annual_return": round(stats["annual_return"], 2),
            "max_drawdown": round(stats["max_drawdown"], 2),
            "max_drawdown_pct": round(stats["max_drawdown_pct"], 2),
            "sharpe_ratio": round(stats["sharpe_ratio"], 2),
            "win_rate": round(stats["win_rate"], 2),
            "total_trades": stats["total_trades"],
            "winning_trades": stats["winning_trades"],
            "losing_trades": stats["losing_trades"],
            "profit_factor": round(stats["profit_factor"], 2),
            "equity_curve": equity_curve,
            "trade_records": trades,
        }

    def _simulate(self, df: pd.DataFrame, initial_capital: float,
                  commission_rate: float, slippage: float) -> tuple:
        """Simulate trading on signal data."""

        capital = initial_capital
        position = 0.0
        equity = initial_capital
        trades = []
        equity_curve = []

        prev_buy_signal = False
        prev_sell_signal = False

        for idx, row in df.iterrows():
            price = row["close"]
            buy_signal = row.get("buy_signal", False)
            sell_signal = row.get("sell_signal", False)

            # Process signals
            if buy_signal and not prev_buy_signal and capital > 0:
                # Buy: use all capital
                buy_amount = capital * 0.95  # Use 95% of capital
                shares = buy_amount / (price * (1 + slippage))
                cost = shares * price * (1 + slippage)
                commission = max(cost * commission_rate, 5.0)
                total_cost = cost + commission
                if total_cost <= capital:
                    position += shares
                    capital -= total_cost
                    trades.append({
                        "date": row["date"],
                        "side": "buy",
                        "price": round(price, 2),
                        "quantity": round(shares, 2),
                        "amount": round(total_cost, 2),
                        "commission": round(commission, 2),
                        "pnl": 0,
                    })

            elif sell_signal and not prev_sell_signal and position > 0:
                # Sell all
                sell_value = position * price * (1 - slippage)
                commission = max(sell_value * commission_rate, 5.0)
                total_received = sell_value - commission
                pnl = total_received - (position * price)  # Simplified PnL
                trades.append({
                    "date": row["date"],
                    "side": "sell",
                    "price": round(price, 2),
                    "quantity": round(position, 2),
                    "amount": round(sell_value, 2),
                    "commission": round(commission, 2),
                    "pnl": round(pnl, 2),
                })
                capital += total_received
                position = 0.0

            # Record equity
            equity = capital + position * price
            equity_curve.append({
                "date": row["date"],
                "equity": round(equity, 2),
            })

            prev_buy_signal = buy_signal
            prev_sell_signal = sell_signal

        # Calculate statistics
        final_capital = capital + position * df["close"].iloc[-1]
        total_return = final_capital - initial_capital
        total_return_pct = (final_capital / initial_capital - 1) * 100

        # Annualized return
        days = len(df)
        years = days / 252
        annual_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Max drawdown
        equity_values = [e["equity"] for e in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        max_dd_pct = 0
        for ev in equity_values:
            if ev > peak:
                peak = ev
            dd = peak - ev
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        # Sharpe ratio (simplified, assuming 0% risk-free rate)
        daily_returns = []
        for i in range(1, len(equity_values)):
            r = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            daily_returns.append(r)
        sharpe = 0
        if daily_returns:
            avg_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe = (avg_return / std_return * math.sqrt(252)) if std_return > 0 else 0

        # Trade statistics
        winning_trades = len([t for t in trades if t["side"] == "sell" and t.get("pnl", 0) > 0])
        losing_trades = len([t for t in trades if t["side"] == "sell" and t.get("pnl", 0) <= 0])
        total_sells = winning_trades + losing_trades
        win_rate = (winning_trades / total_sells * 100) if total_sells > 0 else 0

        # Profit factor
        gross_profit = sum(t.get("pnl", 0) for t in trades if t["side"] == "sell" and t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t["side"] == "sell" and t.get("pnl", 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1)

        stats = {
            "final_capital": final_capital,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "annual_return": annual_return,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "total_trades": len(trades),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "profit_factor": profit_factor,
        }

        return equity_curve, trades, stats


backtest_engine = BacktestEngine()
