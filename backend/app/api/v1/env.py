"""Market Environment API routes (Core 1)."""

import asyncio

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.engine.market_env_engine import market_env_engine
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/env", tags=["Market Environment"])


@router.get("/status")
async def get_env_status(current_user: User = Depends(get_current_user)):
    """Get the current market environment status.

    Returns bull/bear/neutral state with detailed signals and warnings.
    """
    try:
        status = await asyncio.to_thread(market_env_engine.check_environment)
        return {"data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"环境判断失败: {e}")


@router.get("/history")
def get_env_history(
    limit: int = Query(60, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get historical environment records."""
    from app.models.market_env import MarketEnvRecord

    records = (
        db.query(MarketEnvRecord)
        .order_by(MarketEnvRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"data": [r.to_dict() for r in records]}


@router.get("/avg-price-kline")
async def get_avg_price_kline(
    count: int = Query(120, ge=20, le=500),
    current_user: User = Depends(get_current_user),
):
    """Get K-line data for the average stock price (cross-section / configured index)."""
    try:
        result = await asyncio.to_thread(data_engine.get_avg_price_kline, count)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取平均股价K线失败: {e}")


@router.get("/avg-price-snapshot")
async def get_avg_price_snapshot(current_user: User = Depends(get_current_user)):
    """Get a quick snapshot of the current average stock price."""
    try:
        env = await asyncio.to_thread(market_env_engine.check_environment)
        return {
            "data": {
                "avg_price": env.get("avg_price", 0),
                "ma20": env.get("ma20", 0),
                "ma5": env.get("ma5", 0),
                "ma10": env.get("ma10", 0),
                "ma60": env.get("ma60", 0),
                "dist_ma20_pct": env.get("dist_ma20_pct", 0),
                "bull_score": env.get("bull_score", 0),
                "bear_score": env.get("bear_score", 0),
                "overheated": env.get("overheated", False),
                "env_state": env.get("env_state", "unknown"),
                "can_trade": env.get("can_trade", False),
                "message": env.get("message", ""),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
