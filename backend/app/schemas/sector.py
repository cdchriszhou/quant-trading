"""Sector API schemas."""

from pydantic import BaseModel
from typing import Optional


class SectorRankingItem(BaseModel):
    """Single sector ranking entry."""
    sector_code: str
    sector_name: str
    strength_score: float
    rank: int
    ma_alignment: str
    change_20d: float
    limit_up_count: int = 0
    leading_stock: str = ""
    is_blacklisted: bool = False


class SectorRankingResponse(BaseModel):
    """Full ranking response."""
    date: str
    top_sectors: list
    blacklisted_sectors: list = []
    avg_stock_price_change: float = 0.0
