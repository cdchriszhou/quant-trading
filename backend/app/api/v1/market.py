"""Market data API routes."""

from fastapi import APIRouter, Query
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/overview")
def get_market_overview():
    return data_engine.get_market_overview()


@router.get("/quote")
def get_quote(symbol: str = Query("000001.SZ", description="股票代码")):
    return data_engine.get_realtime_quote(symbol)


@router.get("/kline")
def get_kline(
    symbol: str = Query("000001.SZ"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    count: int = Query(100, description="数据条数"),
):
    return {"data": data_engine.get_kline_data(symbol, period, count)}


@router.get("/symbols")
def search_symbols(query: str = Query("", description="搜索关键字")):
    return {"data": data_engine.search_symbols(query)}
