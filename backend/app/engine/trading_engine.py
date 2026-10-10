"""Trading Engine: Paper/live order execution and position management."""

import datetime
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.trade import Trade
from app.models.position import Position as PositionModel
from app.engine.data_engine import data_engine
from app.engine.fee_engine import fee_engine
from app.engine.broker import get_broker
from app.engine.market_calendar import trading_day_start

# A-share lot size (主板/创业板常见 100 股一手)
LOT_SIZE = 100


class TradingEngineError(ValueError):
    """Raised when an order fails pre-trade validation."""


logger = logging.getLogger("trading_engine")


class TradingEngine:
    """Handles order placement, execution, and position management."""

    def get_user_mode(self, db: Session, user_id: int) -> str:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        mode = getattr(user, "account_mode", None) if user else None
        return mode or settings.TRADING_MODE or "paper"

    def set_user_mode(self, db: Session, user_id: int, mode: str) -> str:
        """Persist account mode (paper|live) on the user row."""
        if mode not in ("paper", "live"):
            raise TradingEngineError("mode 仅支持 paper / live")
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise TradingEngineError("用户不存在")
        user.account_mode = mode
        db.commit()
        return mode

    def resolve_trade_mode(
        self,
        db: Session,
        user_id: Optional[int] = None,
        strategy_id: Optional[int] = None,
        mode_override: Optional[str] = None,
    ) -> str:
        """Resolve trade mode from override → strategy → user preference."""
        trade_mode = settings.TRADING_MODE
        if user_id:
            trade_mode = self.get_user_mode(db, user_id)
        if strategy_id:
            from app.models.strategy import Strategy
            strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if strat and strat.mode:
                trade_mode = strat.mode
        if mode_override:
            trade_mode = mode_override

        if trade_mode == "live":
            if not settings.ALLOW_LIVE_TRADING:
                raise TradingEngineError(
                    "实盘开关未打开（ALLOW_LIVE_TRADING=false）。"
                    "行情仍为真实数据；资金请先用模拟账户，或在系统管理→实盘接入中开启。"
                )
            broker = get_broker("live")
            try:
                st = broker.status(connect=False)
            except TypeError:
                st = broker.status()
            connected = bool(getattr(st, "connected", False))
            message = getattr(st, "message", "") or ""
            if not connected:
                try:
                    st = broker.status(connect=True)
                except TypeError:
                    st = broker.status()
                connected = bool(getattr(st, "connected", False))
                message = getattr(st, "message", "") or ""
            if not connected:
                raise TradingEngineError(
                    f"实盘通道未就绪：{message or '请配置 QMT_MINI_PATH / QMT_ACCOUNT_ID'}"
                )
        return trade_mode or "paper"

    def get_cash_balance(
        self, db: Session, user_id: int, trade_mode: Optional[str] = None
    ) -> float:
        """Available cash for the given account mode."""
        mode = trade_mode or self.get_user_mode(db, user_id)
        if mode == "live":
            return float(get_broker("live").get_cash())

        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        initial = float(user.initial_cash) if user else float(settings.DEFAULT_CASH)
        trades = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.trade_mode == "paper",
        ).all()
        total_bought = sum(t.amount + t.commission for t in trades if t.side == "buy")
        total_sold = sum(t.amount - t.commission for t in trades if t.side == "sell")
        return initial - total_bought + total_sold

    def get_available_quantity(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        strategy_id: Optional[int],
        trade_mode: str,
    ) -> float:
        """T+1 available shares = position qty minus today's buys."""
        position = db.query(PositionModel).filter(
            PositionModel.user_id == user_id,
            PositionModel.symbol == symbol,
            PositionModel.strategy_id == strategy_id,
            PositionModel.trade_mode == trade_mode,
            PositionModel.quantity > 0,
        ).first()
        if not position:
            return 0.0

        today_start = trading_day_start()
        q = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.symbol == symbol,
            Trade.side == "buy",
            Trade.trade_mode == trade_mode,
            Trade.trade_time >= today_start,
        )
        if strategy_id is None:
            q = q.filter(Trade.strategy_id.is_(None))
        else:
            q = q.filter(Trade.strategy_id == strategy_id)
        locked = sum(float(t.quantity) for t in q.all())
        return max(0.0, float(position.quantity) - locked)

    def settle_t1_positions(self, db: Session, user_id: Optional[int] = None) -> int:
        """Refresh available_quantity display from T+1 rules."""
        query = db.query(PositionModel).filter(PositionModel.quantity > 0)
        if user_id is not None:
            query = query.filter(PositionModel.user_id == user_id)
        n = 0
        for pos in query.all():
            avail = self.get_available_quantity(
                db, pos.user_id, pos.symbol, pos.strategy_id, pos.trade_mode
            )
            if float(pos.available_quantity or 0) != avail:
                pos.available_quantity = avail
                n += 1
        if n:
            db.commit()
        return n

    @staticmethod
    def normalize_quantity(quantity: float, side: str) -> float:
        """Round buy qty down to lot size; keep sell as-is (validated later)."""
        if quantity <= 0:
            return 0.0
        if side == "buy":
            lots = int(quantity // LOT_SIZE)
            return float(lots * LOT_SIZE)
        return float(quantity)

    def place_order(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        strategy_id: Optional[int] = None,
        remark: str = "",
        mode_override: Optional[str] = None,
    ) -> Order:
        """Place a new order using real quotes + real fees."""
        trade_mode = self.resolve_trade_mode(db, user_id, strategy_id, mode_override)

        quote = data_engine.get_realtime_quote(symbol)
        if quote.get("data_source") == "simulated" or quote.get("_fallback"):
            raise TradingEngineError("行情为非真实数据，已拒绝下单")
        current_price = float(quote["current_price"])
        order_price = float(price) if price else current_price
        if order_price <= 0:
            raise TradingEngineError("无效成交价格")

        quantity = self.normalize_quantity(quantity, side)
        if quantity <= 0:
            raise TradingEngineError(
                "买入数量不足一手（100股）" if side == "buy" else "卖出数量无效"
            )

        # Paper: validate local ledger; Live: broker validates cash/position
        if trade_mode == "paper":
            self._validate_funds_and_position(
                db, user_id, symbol, side, quantity, order_price, strategy_id, trade_mode
            )

        order = Order(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            order_type=order_type,
            side=side,
            price=order_price,
            quantity=quantity,
            status="pending",
            trade_mode=trade_mode,
            remark=remark,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        if trade_mode == "live":
            result = get_broker("live").place_order(
                symbol, side, order_type, quantity, order_price
            )
            if not result.success:
                order.status = "rejected"
                order.remark = (order.remark or "") + f" | {result.message}"
                order.updated_at = datetime.datetime.utcnow()
                db.commit()
                raise TradingEngineError(result.message)
            order.status = result.status or "submitted"
            order.remark = (order.remark or "") + f" | broker:{result.broker_order_id}"
            order.updated_at = datetime.datetime.utcnow()
            # Book immediately when broker reports a fill
            if (result.status or "").lower() == "filled" and (
                result.filled_price or order_price
            ):
                fill_px = float(result.filled_price or order_price)
                if result.filled_quantity and float(result.filled_quantity) > 0:
                    order.quantity = float(result.filled_quantity)
                self._execute_order(db, order, fill_px)
            else:
                db.commit()
            return order

        # Paper: market fills immediately; limit waits for match_pending_limits
        if order_type == "market":
            self._execute_order(db, order, current_price)
        elif order_type == "limit":
            if self._limit_can_fill(side, order_price, current_price):
                self._execute_order(db, order, current_price)

        return order

    @staticmethod
    def _limit_can_fill(side: str, limit_price: float, market_price: float) -> bool:
        if market_price <= 0:
            return False
        if side == "buy":
            return market_price <= limit_price + 1e-9
        return market_price >= limit_price - 1e-9

    def match_pending_limits(self, db: Session, user_id: Optional[int] = None) -> int:
        """Fill paper limit orders when market price crosses limit."""
        q = db.query(Order).filter(
            Order.status == "pending",
            Order.order_type == "limit",
            Order.trade_mode == "paper",
        )
        if user_id is not None:
            q = q.filter(Order.user_id == user_id)
        orders = q.all()
        if not orders:
            return 0

        symbols = list({o.symbol for o in orders if o.symbol})
        quote_map: dict = {}
        try:
            quote_map = data_engine.get_realtime_quotes_batch(symbols) or {}
        except Exception:
            quote_map = {}

        filled = 0
        for order in orders:
            try:
                quote = quote_map.get(order.symbol)
                if not quote:
                    quote = data_engine.get_realtime_quote(order.symbol)
                px = float(quote.get("current_price") or 0)
                if self._limit_can_fill(order.side, float(order.price or 0), px):
                    self._execute_order(db, order, px)
                    filled += 1
            except Exception:
                continue
        return filled

    def sync_live_orders(self, db: Session, user_id: Optional[int] = None) -> int:
        """Poll broker for submitted live orders and book fills / cancellations."""
        q = db.query(Order).filter(
            Order.trade_mode == "live",
            Order.status == "submitted",
        )
        if user_id is not None:
            q = q.filter(Order.user_id == user_id)
        broker = get_broker("live")
        synced = 0
        for order in q.all():
            broker_id = ""
            remark = order.remark or ""
            if "broker:" in remark:
                broker_id = remark.split("broker:")[-1].split()[0].strip(" |")
            if not broker_id:
                continue
            try:
                result = broker.query_order(broker_id)
            except Exception:
                continue
            status = (result.status or "").lower()
            if status == "filled" and (result.filled_price or order.price):
                fill_px = float(result.filled_price or order.price or 0)
                if result.filled_quantity and float(result.filled_quantity) > 0:
                    order.quantity = float(result.filled_quantity)
                try:
                    self._execute_order(db, order, fill_px)
                    synced += 1
                except TradingEngineError:
                    continue
            elif status == "cancelled":
                order.status = "cancelled"
                order.updated_at = datetime.datetime.utcnow()
                order.remark = (order.remark or "") + " | broker-cancelled"
                db.commit()
                synced += 1
        return synced

    def _validate_funds_and_position(
        self,
        db: Session,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        strategy_id: Optional[int],
        trade_mode: str,
    ) -> None:
        if side == "buy":
            need = fee_engine.buy_cost(price, quantity)
            cash = self.get_cash_balance(db, user_id, trade_mode)
            if need > cash + 1e-6:
                raise TradingEngineError(
                    f"可用资金不足：需要 {need:.2f}（含佣金/过户费），可用 {cash:.2f}"
                )
            return

        position = db.query(PositionModel).filter(
            PositionModel.user_id == user_id,
            PositionModel.symbol == symbol,
            PositionModel.strategy_id == strategy_id,
            PositionModel.trade_mode == trade_mode,
            PositionModel.quantity > 0,
        ).first()
        if not position:
            raise TradingEngineError(f"无持仓可卖：{symbol}")
        available = self.get_available_quantity(
            db, user_id, symbol, strategy_id, trade_mode
        )
        if quantity > available + 1e-9:
            raise TradingEngineError(
                f"可卖数量不足：请求 {quantity}，可卖 {available}（T+1）"
            )

    def _execute_order(self, db: Session, order: Order, execution_price: float):
        """Execute a paper (or immediately-filled) order with real fee schedule."""
        if order.status == "filled":
            return  # idempotent — avoid double booking on concurrent sync
        if order.status in ("cancelled", "rejected"):
            raise TradingEngineError(f"订单已结束，无法成交：{order.status}")

        fees = fee_engine.calculate(order.side, execution_price, order.quantity)
        amount = fees.amount
        total_fee = fees.total

        try:
            if order.trade_mode == "paper":
                self._validate_funds_and_position(
                    db,
                    order.user_id,
                    order.symbol,
                    order.side,
                    order.quantity,
                    execution_price,
                    order.strategy_id,
                    order.trade_mode,
                )
        except TradingEngineError as exc:
            order.status = "rejected"
            order.remark = (order.remark or "") + f" | rejected: {exc}"
            order.updated_at = datetime.datetime.utcnow()
            db.commit()
            raise

        order.filled_quantity = order.quantity
        order.commission = total_fee
        order.status = "filled"
        order.updated_at = datetime.datetime.utcnow()
        order.remark = (
            (order.remark or "")
            + f" | fee佣金{fees.commission:.2f}/印花税{fees.stamp_duty:.2f}/过户费{fees.transfer_fee:.2f}"
        )

        trade = Trade(
            user_id=order.user_id,
            strategy_id=order.strategy_id,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=execution_price,
            quantity=order.quantity,
            amount=amount,
            commission=total_fee,
            pnl=0,
            trade_mode=order.trade_mode,
        )

        position = db.query(PositionModel).filter(
            PositionModel.user_id == order.user_id,
            PositionModel.symbol == order.symbol,
            PositionModel.strategy_id == order.strategy_id,
            PositionModel.trade_mode == order.trade_mode,
        ).first()

        if order.side == "buy":
            # Cost basis includes buy fees so sell PnL is net of round-trip costs
            lot_cost = execution_price * order.quantity + total_fee
            if position:
                new_quantity = position.quantity + order.quantity
                new_cost = (
                    position.avg_cost * position.quantity + lot_cost
                ) / new_quantity
                position.quantity = new_quantity
                position.available_quantity = float(position.available_quantity or 0)
                position.avg_cost = round(new_cost, 4)
            else:
                position = PositionModel(
                    user_id=order.user_id,
                    strategy_id=order.strategy_id,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    available_quantity=0.0,
                    avg_cost=round(lot_cost / order.quantity, 4) if order.quantity else execution_price,
                    current_price=execution_price,
                    market_value=amount,
                    unrealized_pnl=0,
                    unrealized_pnl_pct=0,
                    realized_pnl=0,
                    trade_mode=order.trade_mode,
                )
            db.add(position)
        else:
            if not position:
                order.status = "rejected"
                db.commit()
                raise TradingEngineError(f"无持仓可卖：{order.symbol}")

            sell_qty = min(
                order.quantity,
                self.get_available_quantity(
                    db, order.user_id, order.symbol, order.strategy_id, order.trade_mode
                ),
            )
            if sell_qty <= 0:
                order.status = "rejected"
                db.commit()
                raise TradingEngineError("可卖数量为 0（T+1）")

            # avg_cost already embeds buy fees; subtract sell fees only
            realized_pnl = (execution_price - position.avg_cost) * sell_qty - total_fee
            trade.pnl = round(realized_pnl, 2)
            trade.quantity = sell_qty
            trade.amount = execution_price * sell_qty
            # Recalc fee for possibly reduced qty
            fees = fee_engine.calculate(order.side, execution_price, sell_qty)
            trade.commission = fees.total
            trade.pnl = round(
                (execution_price - position.avg_cost) * sell_qty - fees.total, 2
            )
            order.filled_quantity = sell_qty
            order.quantity = sell_qty
            order.commission = fees.total

            position.quantity -= sell_qty
            position.realized_pnl = float(position.realized_pnl or 0) + float(trade.pnl or 0)
            if position.quantity <= 1e-9:
                db.delete(position)
            else:
                position.available_quantity = self.get_available_quantity(
                    db, order.user_id, order.symbol, order.strategy_id, order.trade_mode
                )
                position.current_price = execution_price
                position.market_value = position.quantity * execution_price
                position.unrealized_pnl = round(
                    (execution_price - position.avg_cost) * position.quantity, 2
                )

        db.add(trade)
        db.commit()

    # ── Order management ───────────────────────────────────────────

    def cancel_order(self, db: Session, order_id: int, user_id: int) -> Optional[Order]:
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status.in_(("pending", "submitted")),
        ).first()
        if not order:
            return None

        if order.trade_mode == "live" and order.status == "submitted":
            broker_id = ""
            remark = order.remark or ""
            if "broker:" in remark:
                broker_id = remark.split("broker:")[-1].split()[0].strip(" |")
            if not broker_id:
                raise TradingEngineError(
                    "实盘委托缺少券商单号，无法安全撤单。请在券商端确认后人工对账"
                )
            result = get_broker("live").cancel_order(broker_id)
            if not result.success:
                raise TradingEngineError(result.message or "券商撤单失败")
            order.remark = (order.remark or "") + f" | cancel:{result.message}"

        order.status = "cancelled"
        order.updated_at = datetime.datetime.utcnow()
        db.commit()
        return order

    def get_orders(self, db: Session, user_id: int, status: Optional[str] = None,
                   limit: int = 50) -> list:
        mode = self.get_user_mode(db, user_id)
        query = db.query(Order).filter(
            Order.user_id == user_id,
            Order.trade_mode == mode,
        )
        if status:
            query = query.filter(Order.status == status)
        orders = query.order_by(Order.created_at.desc()).limit(limit).all()
        return [o.to_dict() for o in orders]

    def get_positions(self, db: Session, user_id: int) -> list:
        mode = self.get_user_mode(db, user_id)
        self.settle_t1_positions(db, user_id)
        positions = db.query(PositionModel).filter(
            PositionModel.user_id == user_id,
            PositionModel.trade_mode == mode,
            PositionModel.quantity > 0,
        ).all()

        symbols = list({p.symbol for p in positions if p.symbol})
        quote_map: dict = {}
        if symbols:
            try:
                quote_map = data_engine.batch_get_quotes(symbols) or {}
            except Exception:
                quote_map = {}
            if not quote_map:
                try:
                    quote_map = data_engine.get_realtime_quotes_batch(symbols) or {}
                except Exception:
                    quote_map = {}

        # Realized PnL from sell trades (survives full-close + rebuy; row field alone does not)
        realized_map: dict[tuple, float] = {}
        if symbols:
            from sqlalchemy import func

            sell_rows = (
                db.query(
                    Trade.symbol,
                    Trade.strategy_id,
                    func.coalesce(func.sum(Trade.pnl), 0.0),
                )
                .filter(
                    Trade.user_id == user_id,
                    Trade.side == "sell",
                    Trade.trade_mode == mode,
                    Trade.symbol.in_(symbols),
                )
                .group_by(Trade.symbol, Trade.strategy_id)
                .all()
            )
            for sym, sid, total in sell_rows:
                realized_map[(sym, sid)] = float(total or 0)
            # Also aggregate by symbol only (manual trades often have strategy_id=None
            # while strategy fills use an id — sum all sells for the symbol as fallback)
            sell_by_sym = (
                db.query(Trade.symbol, func.coalesce(func.sum(Trade.pnl), 0.0))
                .filter(
                    Trade.user_id == user_id,
                    Trade.side == "sell",
                    Trade.trade_mode == mode,
                    Trade.symbol.in_(symbols),
                )
                .group_by(Trade.symbol)
                .all()
            )
            realized_by_symbol = {sym: float(total or 0) for sym, total in sell_by_sym}
        else:
            realized_by_symbol = {}

        result = []
        for pos in positions:
            quote = {}
            try:
                quote = quote_map.get(pos.symbol) or {}
                if not quote:
                    quote = data_engine.get_realtime_quote(pos.symbol) or {}
                pos.current_price = float(quote.get("current_price") or 0) or (
                    pos.current_price or pos.avg_cost
                )
            except Exception:
                pos.current_price = pos.current_price or pos.avg_cost
                quote = {}

            pos.market_value = round(pos.quantity * pos.current_price, 2)
            pos.unrealized_pnl = round(
                (pos.current_price - pos.avg_cost) * pos.quantity, 2
            )
            pos.unrealized_pnl_pct = round(
                (pos.current_price - pos.avg_cost) / pos.avg_cost * 100, 2
            ) if pos.avg_cost > 0 else 0
            pos.available_quantity = self.get_available_quantity(
                db, pos.user_id, pos.symbol, pos.strategy_id, pos.trade_mode
            )

            key = (pos.symbol, pos.strategy_id)
            realized = realized_map.get(key)
            if realized is None:
                realized = realized_by_symbol.get(pos.symbol, float(pos.realized_pnl or 0))
            pos.realized_pnl = round(float(realized or 0), 2)

            pre_close = float(quote.get("pre_close") or 0)
            if pre_close <= 0 and pos.current_price > 0:
                # Fallback: derive from change_pct when quote lacks pre_close
                chg = float(quote.get("change_pct") or 0)
                if chg != 0 and chg != -100:
                    pre_close = round(pos.current_price / (1 + chg / 100), 4)
            day_pnl = (
                round((pos.current_price - pre_close) * pos.quantity, 2)
                if pre_close > 0
                else 0.0
            )
            day_pnl_pct = (
                round((pos.current_price - pre_close) / pre_close * 100, 2)
                if pre_close > 0
                else 0.0
            )

            row = pos.to_dict()
            row["realized_pnl"] = pos.realized_pnl
            row["pre_close"] = pre_close or None
            row["day_pnl"] = day_pnl
            row["day_pnl_pct"] = day_pnl_pct
            result.append(row)

        db.commit()
        return result

    def get_account_summary(self, db: Session, user_id: int) -> dict:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        mode = self.get_user_mode(db, user_id)
        positions = self.get_positions(db, user_id)

        total_market_value = sum(p["market_value"] for p in positions)
        total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

        realized_trades = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.side == "sell",
            Trade.trade_mode == mode,
        ).all()
        total_realized_pnl = sum(t.pnl for t in realized_trades)
        cash_balance = self.get_cash_balance(db, user_id, mode)

        if mode == "paper":
            initial = float(user.initial_cash) if user else float(settings.DEFAULT_CASH)
        else:
            initial = cash_balance + total_market_value  # no fake baseline

        total_equity = cash_balance + total_market_value
        total_pnl = total_realized_pnl + total_unrealized_pnl
        total_return_pct = (
            ((total_equity - initial) / initial * 100) if mode == "paper" and initial else 0
        )

        try:
            st = get_broker(mode).status(connect=False)
        except TypeError:
            st = get_broker(mode).status()
        broker = st.to_dict() if hasattr(st, "to_dict") else st

        return {
            "account_mode": mode,
            "initial_cash": initial if mode == "paper" else None,
            "cash_balance": round(cash_balance, 2),
            "market_value": round(total_market_value, 2),
            "total_equity": round(total_equity, 2),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "position_count": len(positions),
            "fee_rates": {
                "commission_rate": settings.COMMISSION_RATE,
                "min_commission": settings.MIN_COMMISSION,
                "stamp_duty_rate": settings.STAMP_DUTY_RATE,
                "transfer_fee_rate": settings.TRANSFER_FEE_RATE,
            },
            "broker": broker,
            "data_policy": "realtime_only",
        }

    def get_equity_curve(self, db: Session, user_id: int) -> list:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        mode = self.get_user_mode(db, user_id)
        if mode != "paper":
            return []  # live equity from broker statements not yet synced

        initial = float(user.initial_cash) if user else float(settings.DEFAULT_CASH)
        trades = (
            db.query(Trade)
            .filter(Trade.user_id == user_id, Trade.trade_mode == "paper")
            .order_by(Trade.trade_time.asc(), Trade.id.asc())
            .all()
        )
        if not trades:
            return []

        cash = initial
        holdings = {}
        last_price = {}
        points = []
        for t in trades:
            last_price[t.symbol] = t.price
            if t.side == "buy":
                cash -= t.amount + t.commission
                prev_qty, prev_cost = holdings.get(t.symbol, (0.0, 0.0))
                new_qty = prev_qty + t.quantity
                avg = (
                    (prev_cost * prev_qty + t.price * t.quantity) / new_qty
                    if new_qty > 0 else 0
                )
                holdings[t.symbol] = (new_qty, avg)
            else:
                cash += t.amount - t.commission
                prev_qty, prev_cost = holdings.get(t.symbol, (0.0, 0.0))
                new_qty = prev_qty - t.quantity
                if new_qty <= 1e-9:
                    holdings.pop(t.symbol, None)
                else:
                    holdings[t.symbol] = (new_qty, prev_cost)

            mv = sum(
                qty * last_price.get(sym, cost)
                for sym, (qty, cost) in holdings.items()
            )
            ts = t.trade_time or t.created_at
            points.append({
                "date": ts.strftime("%Y-%m-%d %H:%M") if ts else "",
                "equity": round(cash + mv, 2),
            })
        return points


trading_engine = TradingEngine()
