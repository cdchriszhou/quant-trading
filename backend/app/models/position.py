"""Position model for tracking holdings."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.core.database import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    strategy_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String(32), nullable=False)
    quantity = Column(Float, default=0.0)
    available_quantity = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)  # Average cost price
    current_price = Column(Float, default=0.0)
    market_value = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    trade_mode = Column(String(16), default="paper")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        from app.models.naming import resolve_symbol_name
        qty = float(self.quantity or 0)
        avg = float(self.avg_cost or 0)
        cur = float(self.current_price or 0)
        mv = float(self.market_value or 0)
        if mv <= 0 and cur > 0 and qty > 0:
            mv = round(cur * qty, 2)
        cost_total = round(avg * qty, 2) if avg > 0 and qty > 0 else 0.0
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "name": resolve_symbol_name(self.symbol),
            "symbol_name": resolve_symbol_name(self.symbol),
            "quantity": self.quantity,
            "available_quantity": self.available_quantity,
            "avg_cost": avg,
            "cost_price": avg,  # alias: 购入均价
            "cost_total": cost_total,  # 购入总资金
            "current_price": cur,
            "market_value": mv,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "trade_mode": self.trade_mode,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
