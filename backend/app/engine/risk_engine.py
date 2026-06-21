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
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).all()
            total_market_value = sum(p.quantity * p.current_price for p in positions if p.current_price)
            new_position_value = amount if side == "buy" else 0
            total_value = total_market_value + new_position_value

            user = db.query(User).filter(User.id == user_id).first()
            portfolio_value = user.initial_cash if user else 100000
            return (total_value / portfolio_value * 100) if portfolio_value > 0 else 0

        elif rule.rule_type == "total_stocks":
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).count()
            return positions + (1 if side == "buy" else 0)

        elif rule.rule_type == "daily_loss":
            today = db.query(Trade).filter(
                Trade.user_id == user_id,
                Trade.side == "sell",
                Trade.trade_time >= "2024-01-01",  # Simplified
            ).all()
            daily_loss = sum(abs(t.pnl) for t in today if t.pnl < 0)
            return daily_loss

        elif rule.rule_type == "drawdown":
            positions = db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity > 0,
            ).all()
            max_dd = 0
            for p in positions:
                if p.avg_cost > 0:
                    dd = (p.avg_cost - p.current_price) / p.avg_cost * 100
                    if dd > max_dd:
                        max_dd = dd
            return max_dd

        return 0


risk_engine = RiskEngine()
