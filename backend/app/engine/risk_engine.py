"""Risk Engine: Pre-trade and post-trade risk validation."""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.risk_rule import RiskRule
from app.models.position import Position
from app.models.trade import Trade
from app.models.user import User
from app.engine.data_engine import data_engine


class RiskEngine:
    """Validates trades against risk rules."""

    def check_order(self, db: Session, user_id: int, symbol: str, side: str,
                    quantity: float, price: float, amount: float) -> dict:
        """Check if an order passes all enabled risk rules."""
        rules = db.query(RiskRule).filter(
            RiskRule.user_id == user_id,
            RiskRule.is_enabled == True,
        ).all()

        violations = []
        for rule in rules:
            result = self._check_rule(db, user_id, rule, symbol, side, quantity, price, amount)
            if result:
                violations.append(result)

        return {
            "passed": len(violations) == 0,
            "violations": violations,
        }

    def _check_rule(self, db: Session, user_id: int, rule: RiskRule,
                    symbol: str, side: str, quantity: float,
                    price: float, amount: float) -> Optional[dict]:
        """Check a single risk rule."""
        current_value = self._get_rule_value(db, user_id, rule, symbol, side, quantity, price, amount)
        threshold = rule.threshold

        passed = True
        if rule.operator == "gt":
            passed = current_value > threshold
        elif rule.operator == "lt":
            passed = current_value < threshold
        elif rule.operator == "ge":
            passed = current_value >= threshold
        elif rule.operator == "le":
            passed = current_value <= threshold
        elif rule.operator == "eq":
            passed = current_value == threshold

        if not passed:
            return {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "rule_type": rule.rule_type,
                "operator": rule.operator,
                "threshold": threshold,
                "current_value": round(current_value, 2),
                "action": rule.action,
            }
        return None

    def _get_rule_value(self, db: Session, user_id: int, rule: RiskRule,
                        symbol: str, side: str, quantity: float,
                        price: float, amount: float) -> float:
        """Get current value for a rule type."""
        if rule.rule_type == "order_amount":
            return amount

        elif rule.rule_type == "position_pct":
            # Calculate total market value of current positions
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).all()
            total_market_value = sum(p.quantity * p.current_price for p in positions if p.current_price)
            new_position_value = amount if side == "buy" else 0
            total_value = total_market_value + new_position_value

            # Use current total equity (initial cash + realized PnL + unrealized PnL),
            # not just initial_cash. Otherwise profitable accounts see inflated
            # position percentages.
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return 0

            # Use SQL aggregation for realized PnL and cash flow
            from sqlalchemy import func, case
            agg = db.query(
                func.coalesce(func.sum(case(
                    (Trade.side == "sell", Trade.pnl), else_=0
                )), 0).label("realized_pnl"),
                func.coalesce(func.sum(case(
                    (Trade.side == "buy", Trade.amount + Trade.commission), else_=0
                )), 0).label("total_bought"),
                func.coalesce(func.sum(case(
                    (Trade.side == "sell", Trade.amount - Trade.commission), else_=0
                )), 0).label("total_sold"),
            ).filter(Trade.user_id == user_id).first()

            current_cash = user.initial_cash - float(agg.total_bought) + float(agg.total_sold)
            portfolio_value = current_cash + total_market_value
            return (total_value / portfolio_value * 100) if portfolio_value > 0 else 0

        elif rule.rule_type == "total_stocks":
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).count()
            return positions + (1 if side == "buy" else 0)

        elif rule.rule_type == "drawdown":
            # Use real-time prices for drawdown calculation (not stale DB prices)
            from app.engine.data_engine import data_engine

            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).all()

            if not positions:
                return 0

            # Batch-fetch real-time quotes for all positions
            symbols = [p.symbol for p in positions]
            quotes_map = data_engine.batch_get_quotes(symbols)

            max_dd = 0
            for p in positions:
                quote = quotes_map.get(p.symbol, {})
                current_price = quote.get("current_price", p.current_price or 0)
                if p.avg_cost > 0 and current_price > 0:
                    dd = (p.avg_cost - current_price) / p.avg_cost * 100
                    if dd > max_dd:
                        max_dd = dd
            return max_dd

        elif rule.rule_type == "daily_loss":
            from datetime import datetime as dt
            from sqlalchemy import func

            today_start = dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            daily_loss = db.query(
                func.coalesce(func.sum(func.abs(Trade.pnl)), 0)
            ).filter(
                Trade.user_id == user_id,
                Trade.side == "sell",
                Trade.pnl < 0,
                Trade.trade_time >= today_start,
            ).scalar()
            return float(daily_loss)

        elif rule.rule_type == "max_daily_loss":
            # Global circuit breaker: total realized loss today as % of portfolio
            from datetime import datetime as dt
            from sqlalchemy import func, case

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return 0

            today_start = dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            daily_loss = db.query(
                func.coalesce(func.sum(case((Trade.pnl < 0, Trade.pnl), else_=0)), 0)
            ).filter(
                Trade.user_id == user_id,
                Trade.trade_time >= today_start,
            ).scalar()
            daily_loss_abs = abs(float(daily_loss))

            # Calculate portfolio value
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).all()
            total_mv = sum(p.quantity * (p.current_price or 0) for p in positions)

            agg = db.query(
                func.coalesce(func.sum(case(
                    (Trade.side == "buy", Trade.amount + Trade.commission), else_=0
                )), 0).label("total_bought"),
                func.coalesce(func.sum(case(
                    (Trade.side == "sell", Trade.amount - Trade.commission), else_=0
                )), 0).label("total_sold"),
            ).filter(Trade.user_id == user_id).first()

            current_cash = user.initial_cash - float(agg.total_bought) + float(agg.total_sold)
            portfolio_value = current_cash + total_mv

            return (daily_loss_abs / portfolio_value * 100) if portfolio_value > 0 else 0

        return 0


risk_engine = RiskEngine()
