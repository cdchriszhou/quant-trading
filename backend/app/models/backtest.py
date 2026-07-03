"""Backtest result model."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from app.core.database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    strategy_id = Column(Integer, nullable=True, index=True)
    strategy_name = Column(String(128), nullable=False)
    strategy_type = Column(String(64), nullable=False)
    parameters = Column(JSON, default={})
    symbols = Column(JSON, default=[])
    start_date = Column(String(16), nullable=False)
    end_date = Column(String(16), nullable=False)
    initial_capital = Column(Float, default=100000.0)
    final_capital = Column(Float, default=100000.0)
    total_return = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    annual_return = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    profit_factor = Column(Float, default=0.0)
    equity_curve = Column(JSON, default=[])  # List of {date, equity} dicts
    trade_records = Column(JSON, default=[])  # List of trade dicts
    status = Column(String(16), default="completed")  # running, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "parameters": self.parameters or {},
            "symbols": self.symbols or [],
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "annual_return": self.annual_return,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "profit_factor": self.profit_factor,
            "equity_curve": self.equity_curve or [],
            "trade_records": self.trade_records or [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
