"""Market environment record model — tracks 大盘环境 state over time."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.core.database import Base


class MarketEnvRecord(Base):
    """Daily snapshot of the average-stock-price environment (Core 1)."""

    __tablename__ = "market_env_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(16), nullable=False, index=True)
    avg_price = Column(Float, default=0.0)
    ma20 = Column(Float, default=0.0)
    ma20_slope = Column(Float, default=0.0)  # positive = rising, near-zero = flat, negative = falling
    volume = Column(Float, default=0.0)  # aggregated trading volume of the sample
    env_state = Column(String(16), default="neutral")  # bull, bear, neutral
    signals = Column(JSON, default=[])  # list of active signal strings
    warnings = Column(JSON, default=[])  # list of warning strings
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "avg_price": self.avg_price,
            "ma20": self.ma20,
            "ma20_slope": round(self.ma20_slope, 6),
            "volume": self.volume,
            "env_state": self.env_state,
            "signals": self.signals or [],
            "warnings": self.warnings or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
