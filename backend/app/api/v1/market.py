"""Market data API routes."""

import asyncio

from fastapi import APIRouter, Query, HTTPException
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/overview")
async def get_market_overview():
    try:
        return await asyncio.to_thread(data_engine.get_market_overview)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取大盘概览失败: {e}")


@router.get("/quote")
async def get_quote(symbol: str = Query("000001.SZ", description="股票代码")):
    try:
        q = await asyncio.to_thread(data_engine.get_realtime_quote, symbol)
        q["data_source"] = q.get("data_source") or "realtime"
        return q
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"真实行情获取失败: {e}")


@router.get("/kline")
async def get_kline(
    symbol: str = Query("000001.SZ"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    count: int = Query(100, description="数据条数"),
):
    try:
        data = await asyncio.to_thread(data_engine.get_kline_data, symbol, period, count)
        return {"data": data, "data_source": "realtime"}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"真实K线获取失败: {e}")


@router.get("/symbols")
async def search_symbols(query: str = Query("", description="搜索关键字")):
    data = await asyncio.to_thread(data_engine.search_symbols, query)
    return {"data": data}


@router.get("/sectors")
async def get_sectors(
    count: int = Query(30, ge=5, le=100, description="返回板块数量"),
):
    """获取主流行业板块行情"""
    try:
        data = await asyncio.to_thread(data_engine.get_sectors, count)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取板块数据失败: {e}")


@router.get("/sector-stocks")
async def get_sector_stocks(
    board_code: str = Query(..., description="板块代码，例如 BK0477 或 new_dzxx"),
    count: int = Query(100, ge=10, le=200, description="返回股票数量"),
):
    """获取指定板块的成分股列表"""
    try:
        data = await asyncio.to_thread(data_engine.get_sector_stocks, board_code, count)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取板块成分股失败: {e}")


@router.get("/top-movers")
async def get_top_movers(
    count: int = Query(10, ge=1, le=50),
    market: str = Query("all", description="板块: all / main / star / chinext / bse"),
):
    """获取涨幅Top N 和 跌幅Top N，可按板块筛选"""
    try:
        return await asyncio.to_thread(data_engine.get_top_movers, count, market)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取涨跌幅排行失败: {e}")


@router.get("/avg-price-kline")
async def get_avg_price_kline(
    count: int = Query(120, ge=20, le=500),
):
    """获取平均股价K线数据（近似通达信880003）"""
    try:
        return await asyncio.to_thread(data_engine.get_avg_price_kline, count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取平均股价K线失败: {e}")


@router.get("/sector-kline")
async def get_sector_kline(
    sector_code: str = Query(..., description="板块代码"),
    count: int = Query(80, ge=20, le=200),
):
    """获取指定行业板块的K线数据"""
    try:
        from app.engine.sector_engine import sector_engine

        kline = await asyncio.to_thread(sector_engine._get_sector_kline, sector_code, count)
        if kline:
            return {"data": kline}
        raise HTTPException(status_code=404, detail="板块K线数据获取失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/stock-insight")
async def get_stock_insight(
    symbol: str = Query(..., description="股票代码，如 600519.SH"),
):
    """公司简介 + 行情快照 + 相关新闻/公告（弹窗详情）"""
    try:
        data = await asyncio.to_thread(data_engine.get_stock_insight, symbol)
        return {"data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取股票详情失败: {e}")
