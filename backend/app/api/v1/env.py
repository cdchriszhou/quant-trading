"""Market Environment API routes (Core 1)."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.engine.market_env_engine import market_env_engine
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/env", tags=["Market Environment"])


@router.get("/status")
def get_env_status():
    """Get the current market environment status.

    Returns bull/bear/neutral state with detailed signals and warnings.
    """
    try:
        status = market_env_engine.check_environment()
        return {"data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"环境判断失败: {e}")


@router.get("/history")
def get_env_history(
    limit: int = Query(60, ge=1, le=365),
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
def get_avg_price_kline(
    count: int = Query(120, ge=20, le=500),
):
    """Get K-line data for the average stock price (近似通达信880003)."""
    try:
        result = data_engine.get_avg_price_kline(count)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取平均股价K线失败: {e}")


@router.get("/avg-price-snapshot")
def get_avg_price_snapshot():
    """Get a quick snapshot of the current average stock price."""
    try:
        env = market_env_engine.check_environment()
        return {
            "data": {
                "avg_price": env.get("avg_price", 0),
                "ma20": env.get("ma20", 0),
                "ma5": env.get("ma5", 0),
                "ma10": env.get("ma10", 0),
                "ma60": env.get("ma60", 0),
                "env_state": env.get("env_state", "unknown"),
                "can_trade": env.get("can_trade", False),
                "message": env.get("message", ""),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
