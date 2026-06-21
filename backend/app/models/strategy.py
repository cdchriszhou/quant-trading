"""Strategy model."""

import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, Boolean
from app.core.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    strategy_type = Column(String(64), nullable=False)  # ma, macd, bollinger, grid, dca, custom
    asset_type = Column(String(32), default="stock")  # stock, crypto, fund
    symbols = Column(JSON, default=[])  # List of trading symbols
    parameters = Column(JSON, default={})  # Strategy parameters dict
    time_frame = Column(String(16), default="1d")  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    status = Column(String(16), default="stopped")  # stopped, running, paused
    mode = Column(String(16), default="paper")  # paper, live
    initial_capital = Column(Float, default=100000.0)
    current_capital = Column(Float, default=100000.0)
    total_return = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "strategy_type": self.strategy_type,
            "asset_type": self.asset_type,
            "symbols": self.symbols or [],
            "parameters": self.parameters or {},
            "time_frame": self.time_frame,
            "status": self.status,
            "mode": self.mode,
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "total_return": self.total_return,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "max_drawdown": self.max_drawdown,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
