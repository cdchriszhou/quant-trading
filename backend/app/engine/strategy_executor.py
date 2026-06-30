"""Strategy Executor: Background task scheduler for running strategies."""

import asyncio
import datetime
import logging
from typing import Dict

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.strategy import Strategy
from app.engine.data_engine import data_engine
from app.engine.strategy_engine import strategy_engine
from app.engine.trading_engine import trading_engine
from app.engine.risk_engine import risk_engine
from app.engine.notification_engine import notification_engine
from app.engine.market_env_engine import market_env_engine
from app.engine.sector_engine import sector_engine

logger = logging.getLogger("strategy_executor")


class StrategyExecutor:
    """Manages background asyncio tasks for running strategies.

    Each active strategy gets a periodic loop that:
    1. Fetches market data
    2. Calculates signals
    3. Places orders based on signals (subject to risk checks)
    """

    def __init__(self):
        self._tasks: Dict[int, asyncio.Task] = {}
        self._running = False
        self._interval = 60  # Default check interval in seconds
        self._loop: asyncio.AbstractEventLoop | None = None

    async def startup(self):
        """Scan DB for running strategies and restart them."""
        self._running = True
        self._loop = asyncio.get_running_loop()
        db = SessionLocal()
        try:
            running_strategies = db.query(Strategy).filter(
                Strategy.status == "running",
                Strategy.is_active == True,
            ).all()
            for strat in running_strategies:
                self._create_task(strat.id)
                logger.info(f"[Strategy] Resumed strategy {strat.id}: {strat.name}")
        except Exception as e:
            logger.error(f"[Strategy] Startup error: {e}")
        finally:
            db.close()
        # Keep the executor alive
        while self._running:
            await asyncio.sleep(60)

    async def shutdown(self):
        """Cancel all running strategy tasks."""
        self._running = False
        for strategy_id, task in list(self._tasks.items()):
            task.cancel()
            logger.info(f"[Strategy] Stopped strategy {strategy_id}")
        self._tasks.clear()

    def start_strategy(self, strategy_id: int):
        """Start a strategy by its ID. Safe to call from any thread."""
        if strategy_id in self._tasks:
            return  # Already running
        if self._loop is None:
            logger.error("[Strategy] Executor not started — call startup() first")
            return
        # Schedule task creation on the main event loop (thread-safe)
        asyncio.run_coroutine_threadsafe(
            self._start_strategy_async(strategy_id), self._loop
        )

    async def _start_strategy_async(self, strategy_id: int):
        """Create the task — must run on the event loop thread."""
        if strategy_id not in self._tasks:
            self._create_task(strategy_id)

    def stop_strategy(self, strategy_id: int):
        """Stop a running strategy. Safe to call from any thread."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._stop_strategy_async(strategy_id), self._loop
        )

    async def _stop_strategy_async(self, strategy_id: int):
        """Cancel the task — must run on the event loop thread."""
        task = self._tasks.pop(strategy_id, None)
        if task:
            task.cancel()
            logger.info(f"[Strategy] Stopped strategy {strategy_id}")

    def is_running(self, strategy_id: int) -> bool:
        """Check if a strategy is currently running."""
        return strategy_id in self._tasks

    def _create_task(self, strategy_id: int):
        """Create and register the background task. MUST run on event loop thread."""
        task = asyncio.create_task(self._run_loop(strategy_id))
        self._tasks[strategy_id] = task

    async def _run_loop(self, strategy_id: int):
        """Main execution loop for a single strategy."""
        while True:
            db = SessionLocal()
            try:
                strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
                if not strat or not strat.is_active or strat.status != "running":
                    # Strategy was stopped or deleted
                    break

                if not strat.symbols:
                    await asyncio.sleep(self._interval)
                    continue

                self._execute_signals(db, strat)
                db.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Strategy] Error in strategy {strategy_id}: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
            finally:
                db.close()

            await asyncio.sleep(self._interval)

    def _execute_signals(self, db: Session, strat: Strategy):
        """Fetch data, compute signals, and place orders for one strategy tick.

        Core 1: Checks market environment before any trading.
        Core 2: Filters stocks by top-N bullish sectors for right_side_entry strategy.
        """
        # ── Layer 0: Market Environment Check (Core 1) ──
        env = market_env_engine.check_environment()
        if env["env_state"] == "bear":
            logger.info(
                f"[Strategy] Market BEARISH — locking ALL buy signals "
                f"(strategy {strat.id}: {strat.name})"
            )
            # Only allow sell signals in bearish market
            buy_locked = True
        elif not env.get("can_trade", False):
            logger.info(
                f"[Strategy] Market NEUTRAL — buy signals suppressed "
                f"(strategy {strat.id}: {strat.name})"
            )
            buy_locked = True
        else:
            buy_locked = False

        # ── Layer 1: Sector Filter (Core 2) for right_side_entry ──
        allowed_symbols = set(strat.symbols)
        if strat.strategy_type == "right_side_entry":
            try:
                top_sectors = sector_engine.get_top_sectors(10)
                if top_sectors:
                    sector_stocks = sector_engine.filter_stocks_by_sector(
                        [s["sector_code"] for s in top_sectors],
                        limit_per_sector=30,
                    )
                    if sector_stocks:
                        allowed_symbols = set(sector_stocks) & set(strat.symbols)
                        if not allowed_symbols:
                            logger.info(
                                f"[Strategy] No stocks in top sectors for strategy {strat.id}"
                            )
                        else:
                            logger.info(
                                f"[Strategy] Sector filter: {len(allowed_symbols)}/{len(strat.symbols)} "
                                f"stocks in top {len(top_sectors)} sectors"
                            )
            except Exception as e:
                logger.warning(f"[Strategy] Sector filter error: {e}, using all symbols")
                allowed_symbols = set(strat.symbols)

        for symbol in strat.symbols:
            # Check if stock passes sector filter
            if symbol not in allowed_symbols:
                continue

            # Get recent data for signal calculation
            df = data_engine.get_history_data(
                symbol,
                start_date=(datetime.datetime.now() - datetime.timedelta(days=120)).strftime("%Y-%m-%d"),
                end_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            )
            if df.empty:
                continue

            # Calculate signals
            try:
                signals_df = strategy_engine.calculate_signals(
                    strat.strategy_type, df, strat.parameters
                )
            except ValueError:
                continue

            if signals_df.empty:
                continue

            # Get the latest signal
            latest = signals_df.iloc[-1]
            buy_signal = latest.get("buy_signal", False)
            sell_signal = latest.get("sell_signal", False)

            if not buy_signal and not sell_signal:
                continue

            # ── Suppress buy signals when market is not bullish ──
            if buy_signal and buy_locked:
                logger.info(
                    f"[Strategy] Buy signal suppressed for {symbol}: market not bullish"
                )
                notification_engine.system(
                    user_id=strat.user_id,
                    title="买入信号被拦截",
                    message=f"{symbol} 出现买入信号，但大盘环境不允许多头开仓，已自动跳过。"
                )
                continue

            quote = data_engine.get_realtime_quote(symbol)
            price = quote["current_price"]
            if price <= 0:
                continue

            side = "buy" if buy_signal else "sell"
            quantity = self._calc_quantity(db, strat, price, side)

            if quantity <= 0:
                continue

            # ── Notification: signal detected ──
            signal_strength = latest.get("signal_strength", 0)
            if buy_signal:
                notification_engine.signal_buy(
                    user_id=strat.user_id,
                    symbol=symbol,
                    price=price,
                    strategy_id=strat.id,
                    strategy_name=strat.name,
                    message=f"信号强度: {signal_strength:.2f} | 策略类型: {strat.strategy_type}",
                )
            else:
                # Determine specific sell reason for richer notifications
                if latest.get("stop_loss_hit"):
                    notification_engine.stop_loss(
                        user_id=strat.user_id, symbol=symbol, price=price,
                        strategy_id=strat.id, strategy_name=strat.name,
                    )
                else:
                    reason = f"信号强度: {signal_strength:.2f}"
                    if latest.get("trail_stop_ma5"):
                        reason = "移动止盈: 跌破5日均线"
                    elif latest.get("top_big_drop"):
                        reason = "见顶信号: 长阴破位"
                    elif latest.get("top_stall"):
                        reason = "见顶信号: 放量滞涨"
                    notification_engine.signal_sell(
                        user_id=strat.user_id,
                        symbol=symbol,
                        price=price,
                        strategy_id=strat.id,
                        strategy_name=strat.name,
                        reason=reason,
                    )

            # Risk check
            risk_result = risk_engine.check_order(
                db, strat.user_id, symbol, side, quantity, price, quantity * price
            )
            if not risk_result["passed"]:
                logger.info(
                    f"[Strategy] Risk blocked {strat.id}: {side} {symbol} x{quantity}"
                )
                notification_engine.risk_blocked(
                    user_id=strat.user_id,
                    symbol=symbol,
                    side=side,
                    price=price,
                    strategy_id=strat.id,
                    strategy_name=strat.name,
                    violations=risk_result.get("violations", []),
                )
                continue

            # Place order
            order = trading_engine.place_order(
                db, strat.user_id, symbol, side, "market", quantity, price,
                strategy_id=strat.id, remark=f"Auto: {strat.name}"
            )
            logger.info(
                f"[Strategy] Placed {side} {symbol} x{quantity} @ {price} "
                f"for strategy {strat.id}: {strat.name}"
            )

            # ── Notification: order placed ──
            notification_engine.order_placed(
                user_id=strat.user_id,
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                strategy_id=strat.id,
                strategy_name=strat.name,
                order_id=order.id if order else 0,
            )

    def _calc_quantity(self, db: Session, strat: Strategy, price: float, side: str) -> float:
        """Calculate order quantity based on strategy type and capital."""
        if side == "sell":
            # Sell all existing position for this symbol + strategy
            from app.models.position import Position as PositionModel
            pos = db.query(PositionModel).filter(
                PositionModel.user_id == strat.user_id,
                PositionModel.strategy_id == strat.id,
                PositionModel.quantity > 0,
            ).first()
            return pos.quantity if pos else 0

        # Buy: use a portion of strategy capital
        if strat.strategy_type == "dca":
            fixed_amount = float(strat.parameters.get("fixed_amount", 1000))
            return fixed_amount / price if price > 0 else 0

        # Default: use 20% of remaining cash per signal
        from app.models.trade import Trade
        from app.models.user import User
        user = db.query(User).filter(User.id == strat.user_id).first()
        trades = db.query(Trade).filter(Trade.user_id == strat.user_id).all()
        total_bought = sum(t.amount + t.commission for t in trades if t.side == "buy")
        total_sold = sum(t.amount - t.commission for t in trades if t.side == "sell")
        cash = (user.initial_cash if user else 100000) - total_bought + total_sold
        buy_amount = cash * 0.2
        return buy_amount / price if price > 0 else 0


strategy_executor = StrategyExecutor()
