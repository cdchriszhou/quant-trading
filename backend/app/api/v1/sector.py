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
            stocks = data_engine.get_sector_stocks(
                code, count=stocks_per_sector * 3, sector_name=name,
            )
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


def _quote_to_screening(stock: dict) -> dict:
    """Build a display dict from quote data (no heavy screening)."""
    return {
        "symbol": stock["code"],
        "name": stock.get("name", stock["code"]),
        "current_price": stock.get("price", 0),
        "change_pct": stock.get("change_pct", 0),
        "criteria_met": None,
        "buy_signal": False,
    }


def _safe_screen_symbol(sym: str, quote: dict | None = None, timeout: float = 10.0) -> dict:
    """Screen one symbol with timeout; fall back to quote data on failure."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(stock_screener.check_criteria, sym)
            return future.result(timeout=timeout)
    except (FuturesTimeout, Exception):
        result = stock_screener._empty_result(sym, "筛选超时")
        if quote:
            result["name"] = quote.get("name", sym)
            result["current_price"] = quote.get("price", 0)
        return result


@router.get("/{sector_code}/stocks")
def get_sector_stocks(
    sector_code: str,
    sector_name: str | None = Query(None, description="板块名称（可选，加快查询）"),
    screened: bool = Query(True, description="是否应用个股筛选条件"),
    limit: int = Query(30, ge=10, le=100),
):
    """Get stocks within a sector, optionally screened for quality."""
    from app.engine.data_engine import data_engine
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

    try:
        if not sector_name:
            ranking = sector_engine.rank_sectors()
            sector_info = next((s for s in ranking if s["sector_code"] == sector_code), None)
            sector_name = sector_info["sector_name"] if sector_info else None

        stocks = data_engine.get_sector_stocks(
            sector_code, count=limit, sector_name=sector_name,
        )
        if not stocks:
            return {"data": [], "message": "板块成分股获取失败，请稍后重试"}

        if not screened:
            return {
                "data": [_quote_to_screening(s) for s in stocks],
                "total": len(stocks),
                "screened": False,
                "message": f"共 {len(stocks)} 只成分股",
            }

        # Screen at most `limit` stocks with per-symbol timeout (avoid 60s+ hangs)
        quote_map = {s["code"]: s for s in stocks}
        symbols = [s["code"] for s in stocks[:limit]]
        screened_results = []

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_safe_screen_symbol, sym, quote_map.get(sym)): sym
                for sym in symbols
            }
            try:
                for future in as_completed(futures, timeout=75):
                    try:
                        screened_results.append(future.result())
                    except Exception:
                        sym = futures[future]
                        screened_results.append(_safe_screen_symbol(sym, quote_map.get(sym), timeout=0.1))
            except FuturesTimeout:
                for future, sym in futures.items():
                    if not future.done():
                        future.cancel()
                        screened_results.append(_safe_screen_symbol(sym, quote_map.get(sym), timeout=0.1))

        screened_results.sort(
            key=lambda x: (x.get("criteria_met", False), x.get("buy_signal", False)),
            reverse=True,
        )
        passed = sum(1 for s in screened_results if s.get("criteria_met"))
        return {
            "data": screened_results,
            "total": len(screened_results),
            "passed": passed,
            "screened": True,
            "message": f"共 {len(screened_results)} 只，达标 {passed} 只",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取板块成分股失败: {e}")
