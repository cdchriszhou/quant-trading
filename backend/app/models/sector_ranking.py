"""Sector ranking model — tracks industry sector trend strength over time."""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from app.core.database import Base


class SectorRanking(Base):
    """Daily industry sector strength ranking snapshot (Core 2)."""

    __tablename__ = "sector_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(16), nullable=False, index=True)
    sector_code = Column(String(32), nullable=False)
    sector_name = Column(String(64), nullable=False)
    strength_score = Column(Float, default=0.0)  # composite score (0-100)
    rank = Column(Integer, default=0)
    # MA alignment sub-scores
    ma_alignment = Column(String(32), default="")  # "bullish" | "mixed" | "bearish"
    ma5 = Column(Float, default=0.0)
    ma10 = Column(Float, default=0.0)
    ma20 = Column(Float, default=0.0)
    ma60 = Column(Float, default=0.0)
    change_20d = Column(Float, default=0.0)  # 20-day return percentage
    limit_up_count = Column(Integer, default=0)  # daily-limit-up stock count in sector
    leading_stock = Column(String(64), default="")
    leading_stock_code = Column(String(16), default="")
    is_blacklisted = Column(Boolean, default=False)  # weak sector, excluded from screening
    details = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "sector_code": self.sector_code,
            "sector_name": self.sector_name,
            "strength_score": round(self.strength_score, 2),
            "rank": self.rank,
            "ma_alignment": self.ma_alignment,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma60": self.ma60,
            "change_20d": round(self.change_20d, 2),
            "limit_up_count": self.limit_up_count,
            "leading_stock": self.leading_stock,
            "leading_stock_code": self.leading_stock_code,
            "is_blacklisted": self.is_blacklisted,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
