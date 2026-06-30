"""Sector ranking and screening API routes (Core 2)."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.engine.sector_engine import sector_engine
from app.engine.stock_screener import stock_screener

router = APIRouter(prefix="/sectors", tags=["Sector Analysis"])


@router.get("/ranking")
def get_sector_ranking(
    force_refresh: bool = Query(False, description="强制刷新排名"),
    top_n: int = Query(10, ge=5, le=30, description="返回前N个板块"),
):
    """Get all industry sectors ranked by composite trend-strength score.

    Core 2 logic:
      - MA alignment: 5MA > 10MA > 20MA > 60MA
      - Relative performance vs average stock price
      - Limit-up stock count within sector (赚钱效应)
    """
    try:
        ranking = sector_engine.rank_sectors(force_refresh=force_refresh)
        top = [s for s in ranking if not s["is_blacklisted"]][:top_n]
        blacklisted = [s for s in ranking if s["is_blacklisted"]]

        from app.engine.sector_engine import sector_engine as se
        avg_price_change = se._get_avg_price_change_20d()

        return {
            "data": {
                "date": "",  # filled by updated_at
                "top_sectors": top,
                "total_ranked": len(ranking),
                "blacklisted_sectors": blacklisted,
                "avg_stock_price_change_20d": avg_price_change,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"板块排名失败: {e}")


@router.get("/{sector_code}/stocks")
def get_sector_stocks(
    sector_code: str,
    screened: bool = Query(True, description="是否应用个股筛选条件"),
    limit: int = Query(30, ge=10, le=100),
):
    """Get stocks within a sector, optionally screened for quality.

    When screened=True, applies Core 3 criteria:
      1. Price above all short MAs
      2. Up on volume / down on shrinking volume
      3. Higher lows, no breakdowns
      4. Liquidity >= threshold
    """
    try:
        from app.engine.data_engine import data_engine

        stocks = data_engine.get_sector_stocks(sector_code, count=limit * 2)
        if not stocks:
            return {"data": [], "message": "板块成分股获取失败"}

        symbols = [s["code"] for s in stocks]

        if screened:
            screened_results = stock_screener.screen_stocks(symbols, require_signal=False)
            return {
                "data": screened_results[:limit],
                "total": len(screened_results),
                "screened": True,
            }

        return {
            "data": [{"symbol": s["code"], "name": s["name"], "price": s["price"],
                      "change_pct": s.get("change_pct", 0)} for s in stocks[:limit]],
            "total": len(stocks),
            "screened": False,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取板块成分股失败: {e}")


@router.get("/blacklist/view")
def get_blacklisted_sectors():
    """Get currently blacklisted weak sectors."""
    try:
        blacklisted = sector_engine.get_blacklisted_sectors()
        return {"data": blacklisted, "total": len(blacklisted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-stocks")
def get_top_sector_stocks(
    top_n: int = Query(10, ge=5, le=30),
    stocks_per_sector: int = Query(10, ge=5, le=50),
):
    """Get screened stocks from the top-N bullish sectors.

    This is the Core 2 → Core 3 pipeline:
      1. Find top N bullish sectors
      2. Extract constituent stocks
      3. Screen each stock with right-side criteria
      4. Return the best candidates
    """
    try:
        top_sectors = sector_engine.get_top_sectors(top_n)
        if not top_sectors:
            return {"data": [], "message": "当前无符合条件的多头板块"}

        from app.engine.data_engine import data_engine

        all_stocks = []
        seen = set()

        for sec in top_sectors:
            code = sec["sector_code"]
            name = sec["sector_name"]
            stocks = data_engine.get_sector_stocks(code, count=stocks_per_sector * 3)
            for s in stocks:
                sym = s["code"]
                if sym in seen:
                    continue
                seen.add(sym)
                # Quick screen
                screening = stock_screener.check_criteria(sym)
                screening["sector_name"] = name
                screening["sector_code"] = code
                all_stocks.append(screening)

            if len(all_stocks) >= stocks_per_sector * top_n:
                break  # exit outer sector loop, enough stocks collected

        # Sort by buy signal + criteria_met
        scored = []
        for s in all_stocks:
            score = 0
            if s.get("buy_signal"):
                score += 3
            if s.get("criteria_met"):
                score += 2
            if s.get("all_above_ma"):
                score += 1
            scored.append({**s, "_score": score})

        scored.sort(key=lambda x: x["_score"], reverse=True)

        return {
            "data": scored[:stocks_per_sector * top_n],
            "total": len(scored),
            "top_sectors": [{"code": s["sector_code"], "name": s["sector_name"],
                             "score": s["strength_score"]} for s in top_sectors],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"选股失败: {e}")
