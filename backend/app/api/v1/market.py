"""Market data API routes."""

from fastapi import APIRouter, Query, HTTPException
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/overview")
def get_market_overview():
    try:
        return data_engine.get_market_overview()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取大盘概览失败: {e}")


@router.get("/quote")
def get_quote(symbol: str = Query("000001.SZ", description="股票代码")):
    try:
        return data_engine.get_realtime_quote(symbol)
    except RuntimeError as e:
        # Fallback to simulated data when real API is unreachable
        fallback = data_engine.generate_fallback_quote(symbol)
        if fallback:
            fallback["data_source"] = "simulated"
            fallback["_fallback"] = True
            return fallback
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/kline")
def get_kline(
    symbol: str = Query("000001.SZ"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    count: int = Query(100, description="数据条数"),
):
    try:
        return {"data": data_engine.get_kline_data(symbol, period, count)}
    except RuntimeError as e:
        # Fallback to simulated K-line when real API is unreachable
        fallback = data_engine.generate_fallback_kline(symbol, period, count)
        if fallback:
            return {"data": fallback, "_fallback": True}
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols")
def search_symbols(query: str = Query("", description="搜索关键字")):
    return {"data": data_engine.search_symbols(query)}


@router.get("/sectors")
def get_sectors(
    count: int = Query(30, ge=5, le=100, description="返回板块数量"),
):
    """获取主流行业板块行情（申万行业分类）"""
    try:
        return {"data": data_engine.get_sectors(count)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取板块数据失败: {e}")


@router.get("/sector-stocks")
def get_sector_stocks(
    board_code: str = Query(..., description="板块代码，例如 BK0477"),
    count: int = Query(100, ge=10, le=200, description="返回股票数量"),
):
    """获取指定板块的成分股列表"""
    try:
        return {"data": data_engine.get_sector_stocks(board_code, count)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取板块成分股失败: {e}")


@router.get("/top-movers")
def get_top_movers(
    count: int = Query(10, ge=1, le=50),
    market: str = Query("all", description="板块: all / main / star / chinext / bse"),
):
    """获取涨幅Top N 和 跌幅Top N，可按板块筛选"""
    try:
        return data_engine.get_top_movers(count, market=market)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取涨跌幅排行失败: {e}")


@router.get("/avg-price-kline")
def get_avg_price_kline(
    count: int = Query(120, ge=20, le=500),
):
    """获取平均股价K线数据（近似通达信880003）"""
    try:
        return data_engine.get_avg_price_kline(count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取平均股价K线失败: {e}")


@router.get("/sector-kline")
def get_sector_kline(
    sector_code: str = Query(..., description="板块代码"),
    count: int = Query(80, ge=20, le=200),
):
    """获取指定行业板块的K线数据"""
    try:
        from app.engine.sector_engine import sector_engine
        kline = sector_engine._get_sector_kline(sector_code, count)
        if kline:
            return {"data": kline}
        raise HTTPException(status_code=404, detail="板块K线数据获取失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
