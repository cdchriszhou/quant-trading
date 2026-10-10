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
from app.engine.market_calendar import (
    is_a_share_trading_session,
    next_session_hint,
    trading_day_start,
)
from app.engine.fee_engine import fee_engine
from app.models.trade import Trade
from app.models.position import Position as PositionModel

logger = logging.getLogger("strategy_executor")


class StrategyExecutor:
    """Manages background asyncio tasks for running strategies.

    Each active strategy gets a periodic loop that:
    1. Fetches market data
    2. Calculates signals
    3. Places orders based on signals (subject to risk checks)

    Check interval adapts to the strategy's time_frame:
      1m/5m/15m → 15s (intraday, need fast response)
      30m/60m   → 60s
      1d         → 300s (daily bars, 5 min is plenty)
      1w         → 1800s (weekly, check every 30 min)
    """

    # Timeframe → check interval (seconds)
    INTERVAL_MAP = {
        "1m": 15, "5m": 15, "15m": 15,
        "30m": 60, "60m": 60, "1h": 60,
        "1d": 300,
        "1w": 1800,
    }
    DEFAULT_INTERVAL = 60

    def __init__(self):
        self._tasks: Dict[int, asyncio.Task] = {}
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._intervals: Dict[int, int] = {}

    def _interval_for(self, strategy_id: int) -> int:
        return self._intervals.get(strategy_id, self.DEFAULT_INTERVAL)

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
        """Main execution loop for a single strategy.

        Heavy sync IO (history/quotes/DB) runs in a worker thread so the
        asyncio event loop stays responsive for API/WebSocket.
        """
        try:
            while True:
                try:
                    keep_running = await asyncio.to_thread(self._tick_once, strategy_id)
                    if not keep_running:
                        break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[Strategy] Error in strategy {strategy_id}: {e}")
                await asyncio.sleep(self._interval_for(strategy_id))
        finally:
            self._tasks.pop(strategy_id, None)
            self._intervals.pop(strategy_id, None)

    def _tick_once(self, strategy_id: int) -> bool:
        """One synchronous strategy tick. Returns False when the strategy should stop."""
        db = SessionLocal()
        try:
            strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strat or not strat.is_active or strat.status != "running":
                return False

            self._intervals[strategy_id] = self.INTERVAL_MAP.get(
                (strat.time_frame or "1d").lower(), self.DEFAULT_INTERVAL
            )

            if not strat.symbols:
                return True

            try:
                trading_engine.sync_live_orders(db, strat.user_id)
                trading_engine.match_pending_limits(db, strat.user_id)
            except Exception as e:
                logger.warning(f"[Strategy] Order sync skipped: {e}")

            if not is_a_share_trading_session():
                logger.debug(
                    f"[Strategy] Skip new orders ({next_session_hint()}) "
                    f"strategy={strat.id}"
                )
                db.commit()
                return True

            self._execute_signals(db, strat)
            db.commit()
            return True
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            db.close()

    def _execute_signals(self, db: Session, strat: Strategy):
        """Fetch data, compute signals, and place orders for one strategy tick.

        Runs synchronously (called from ``_tick_once`` via ``asyncio.to_thread``).
        """
        # ── Layer 0: Market Environment Check (Core 1) ──
        env = market_env_engine.check_environment()
        env_exposure = float(env.get("exposure_mult") if env.get("exposure_mult") is not None else (
            1.0 if env.get("can_trade") else 0.0
        ))
        if env["env_state"] == "bear":
            logger.info(
                f"[Strategy] Market BEARISH — locking ALL buy signals "
                f"(strategy {strat.id}: {strat.name})"
            )
            buy_locked = True
        elif not env.get("can_trade", False) or env_exposure < 0.15:
            logger.info(
                f"[Strategy] Market NEUTRAL/low-exposure — buy signals suppressed "
                f"(strategy {strat.id}: {strat.name}, exposure={env_exposure})"
            )
            buy_locked = True
        else:
            buy_locked = False
        # Stash for sizing on this tick
        strat._tick_env_exposure = env_exposure  # type: ignore[attr-defined]
        strat._tick_env_shallow = bool((env.get("checklist") or {}).get("shallow_pullback"))  # type: ignore[attr-defined]
        strat._tick_env_msg = env.get("message") or ""  # type: ignore[attr-defined]

        # ── Layer 1: Sector Filter (Core 2) for right_side_entry ──
        # Only blocks new buys; sells on existing holdings still allowed.
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
                logger.warning(f"[Strategy] Sector filter error: {e}, skipping buy opens")
                allowed_symbols = set(strat.symbols)

        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=280)).strftime("%Y-%m-%d")

        quote_map: dict = {}
        try:
            quote_map = data_engine.batch_get_quotes(list(strat.symbols)) or {}
        except Exception as e:
            logger.warning(f"[Strategy] batch quotes skipped: {e}")
            try:
                quote_map = data_engine.get_realtime_quotes_batch(list(strat.symbols)) or {}
            except Exception:
                quote_map = {}

        for symbol in strat.symbols:
            df = data_engine.get_history_data(symbol, start_date, end_date)
            if df is None or getattr(df, "empty", True):
                continue

            try:
                signals_df = strategy_engine.calculate_signals(
                    strat.strategy_type, df, strat.parameters
                )
            except ValueError:
                continue

            if signals_df is None or getattr(signals_df, "empty", True):
                continue

            latest = signals_df.iloc[-1]
            buy_signal = bool(latest.get("buy_signal", False))
            sell_signal = bool(latest.get("sell_signal", False))

            if not buy_signal and not sell_signal:
                continue

            # Prefer sell when both fire
            if buy_signal and sell_signal:
                buy_signal = False

            if buy_signal and symbol not in allowed_symbols:
                continue

            if buy_signal and buy_locked:
                logger.info(
                    f"[Strategy] Buy signal suppressed for {symbol}: market not tradeable "
                    f"({getattr(strat, '_tick_env_msg', '')})"
                )
                notification_engine.system(
                    user_id=strat.user_id,
                    title="买入信号被拦截",
                    message=(
                        f"{symbol} 出现买入信号，但大盘环境不允许开仓"
                        f"（{getattr(strat, '_tick_env_msg', '环境锁定')}），已自动跳过。"
                    ),
                )
                continue

            side = "buy" if buy_signal else "sell"

            if self._already_acted_today(db, strat, symbol, side):
                logger.info(
                    f"[Strategy] Dedup skip {strat.id} {side} {symbol} (already acted today)"
                )
                continue

            if side == "buy" and self._has_open_position(db, strat, symbol):
                logger.info(
                    f"[Strategy] Skip buy {symbol}: already holding for strategy {strat.id}"
                )
                continue

            quote = quote_map.get(symbol)
            if not quote:
                try:
                    quote = data_engine.get_realtime_quote(symbol)
                except Exception:
                    continue
            price = float(quote.get("current_price") or 0)
            if price <= 0:
                continue

            quantity = self._calc_quantity(
                db, strat, price, side, symbol=symbol, price_history=df
            )
            if quantity <= 0:
                continue

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

            order_notional = (
                fee_engine.buy_cost(price, quantity) if side == "buy" else price * quantity
            )
            risk_result = risk_engine.check_order(
                db, strat.user_id, symbol, side, quantity, price, order_notional,
                trade_mode=strat.mode or None,
            )
            if risk_result.get("should_pause"):
                logger.info(f"[Strategy] Risk pause strategy {strat.id}")
                strat.status = "paused"
                strat.is_active = False
                db.commit()
                notification_engine.risk_blocked(
                    user_id=strat.user_id,
                    symbol=symbol,
                    side=side,
                    price=price,
                    strategy_id=strat.id,
                    strategy_name=strat.name,
                    violations=risk_result.get("violations", []),
                )
                self.stop_strategy(strat.id)
                return

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

            for warn in risk_result.get("warnings", []):
                logger.warning(
                    f"[Strategy] Risk warn {strat.id}: {warn.get('rule_name')} "
                    f"{warn.get('current_value')} vs {warn.get('threshold')}"
                )

            try:
                from app.engine.trading_engine import TradingEngineError
                mode = strat.mode or trading_engine.get_user_mode(db, strat.user_id)
                order = trading_engine.place_order(
                    db, strat.user_id, symbol, side, "market", quantity, price,
                    strategy_id=strat.id, remark=f"Auto: {strat.name}",
                    mode_override=mode,
                )
            except Exception as e:
                # TradingEngineError or other reject
                logger.info(f"[Strategy] Order rejected {strat.id}: {e}")
                continue

            logger.info(
                f"[Strategy] Placed {side} {symbol} x{quantity} @ {price} "
                f"for strategy {strat.id}: {strat.name}"
            )
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

    @staticmethod
    def _already_acted_today(db: Session, strat: Strategy, symbol: str, side: str) -> bool:
        """True if this strategy already traded or has open order for symbol+side today."""
        from app.models.order import Order

        day0 = trading_day_start()
        mode = strat.mode or "paper"
        traded = db.query(Trade).filter(
            Trade.user_id == strat.user_id,
            Trade.strategy_id == strat.id,
            Trade.symbol == symbol,
            Trade.side == side,
            Trade.trade_mode == mode,
            Trade.trade_time >= day0,
        ).first()
        if traded:
            return True
        open_order = db.query(Order).filter(
            Order.user_id == strat.user_id,
            Order.strategy_id == strat.id,
            Order.symbol == symbol,
            Order.side == side,
            Order.trade_mode == mode,
            Order.status.in_(("pending", "submitted")),
            Order.created_at >= day0,
        ).first()
        return open_order is not None

    @staticmethod
    def _has_open_position(db: Session, strat: Strategy, symbol: str) -> bool:
        mode = strat.mode or "paper"
        pos = db.query(PositionModel).filter(
            PositionModel.user_id == strat.user_id,
            PositionModel.strategy_id == strat.id,
            PositionModel.symbol == symbol,
            PositionModel.trade_mode == mode,
            PositionModel.quantity > 0,
        ).first()
        return pos is not None

    def _calc_quantity(
        self,
        db: Session,
        strat: Strategy,
        price: float,
        side: str,
        symbol: str = "",
        price_history=None,
    ) -> float:
        """Calculate order quantity with T+1 sells and volatility targeting buys."""
        from app.engine.trading_engine import trading_engine, LOT_SIZE
        import math

        mode = strat.mode or trading_engine.get_user_mode(db, strat.user_id) or "paper"

        if side == "sell":
            return trading_engine.get_available_quantity(
                db, strat.user_id, symbol, strat.id, mode
            )

        if strat.strategy_type == "dca":
            fixed_amount = float((strat.parameters or {}).get("fixed_amount", 1000))
            raw = fixed_amount / price if price > 0 else 0
            return trading_engine.normalize_quantity(raw, "buy")

        cash = max(trading_engine.get_cash_balance(db, strat.user_id, mode), 0.0)
        params = strat.parameters or {}
        target_vol = float(params.get("target_volatility", 0.15))  # annualized
        max_pct = float(params.get("max_position_pct", 0.30))  # of cash
        lookback = int(params.get("vol_lookback", 20))

        # Volatility targeting: size ∝ target_vol / realized_vol
        position_pct = 0.20  # fallback
        if price_history is not None and len(price_history) >= max(lookback + 1, 5):
            try:
                closes = price_history["close"].astype(float)
                rets = closes.pct_change().dropna().tail(lookback)
                daily_vol = float(rets.std())
                if daily_vol > 1e-8:
                    ann_vol = daily_vol * math.sqrt(252)
                    position_pct = target_vol / ann_vol
            except Exception:
                pass

        position_pct = max(0.05, min(position_pct, max_pct))
        # Align auto size with env exposure (shallow pullback → 40~55% of normal)
        env_exp = float(getattr(strat, "_tick_env_exposure", 1.0) or 1.0)
        env_exp = max(0.15, min(1.0, env_exp))
        position_pct *= env_exp
        if getattr(strat, "_tick_env_shallow", False):
            position_pct = min(position_pct, max_pct * 0.5)
            logger.info(
                f"[Strategy] Shallow-pullback size cut → position_pct={position_pct:.3f} "
                f"(env_exp={env_exp})"
            )
        buy_amount = cash * position_pct
        raw = buy_amount / price if price > 0 else 0
        qty = trading_engine.normalize_quantity(raw, "buy")
        # Do NOT force a full lot when env is in reduced-exposure mode
        if qty < LOT_SIZE and env_exp >= 0.85 and cash >= price * LOT_SIZE * 1.002:
            qty = float(LOT_SIZE)
        return qty


strategy_executor = StrategyExecutor()
