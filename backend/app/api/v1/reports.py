"""Reports and statistics API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.trade import Trade
from app.models.order import Order
from app.models.strategy import Strategy
from app.models.operation_log import OperationLog
from app.engine.trading_engine import trading_engine
from app.engine.data_engine import data_engine

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = trading_engine.get_account_summary(db, current_user.id)
    strategies = db.query(Strategy).filter(
        Strategy.user_id == current_user.id,
    ).all()
    running_strategies = sum(1 for s in strategies if s.status == "running")

    # Use proper datetime comparison for today's trades
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades = db.query(func.count(Trade.id)).filter(
        Trade.user_id == current_user.id,
        Trade.trade_time >= today_start,
    ).scalar()

    recent_trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).order_by(Trade.created_at.desc()).limit(10).all()

    try:
        overview = data_engine.get_market_overview()
    except RuntimeError as e:
        overview = {
            "indices": [],
            "data_source": "error",
            "error": str(e),
        }

    return {
        "data": {
            "account": account,
            "total_strategies": len(strategies),
            "running_strategies": running_strategies,
            "today_trades": today_trades,
            "recent_trades": [t.to_dict() for t in recent_trades],
            "market": overview,
        }
    }


@router.get("/trades")
def get_trades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).order_by(Trade.created_at.desc()).limit(100).all()
    return {"data": [t.to_dict() for t in trades]}


@router.get("/performance")
def get_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Performance summary — uses SQL aggregation instead of loading all trades."""
    from sqlalchemy import case

    agg = db.query(
        func.count(Trade.id).label("total_trades"),
        func.coalesce(func.sum(case((Trade.side == "buy", 1), else_=0)), 0).label("buy_trades"),
        func.coalesce(func.sum(case((Trade.side == "sell", 1), else_=0)), 0).label("sell_trades"),
        func.coalesce(func.sum(Trade.commission), 0).label("total_commission"),
        func.coalesce(func.sum(Trade.pnl), 0).label("total_pnl"),
        func.coalesce(func.sum(case((Trade.pnl > 0, 1), else_=0)), 0).label("winning_trades"),
        func.coalesce(func.sum(case((Trade.pnl < 0, 1), else_=0)), 0).label("losing_trades"),
    ).filter(Trade.user_id == current_user.id).first()

    total_trades = agg.total_trades
    buy_trades = int(agg.buy_trades)
    sell_trades = int(agg.sell_trades)
    total_commission = float(agg.total_commission)
    total_pnl = float(agg.total_pnl)
    winning_trades = int(agg.winning_trades)
    losing_trades = int(agg.losing_trades)
    win_rate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0

    account = trading_engine.get_account_summary(db, current_user.id)

    return {
        "data": {
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_commission": round(total_commission, 2),
            "total_pnl": round(total_pnl, 2),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "account": account,
        }
    }


@router.get("/trades/export")
def export_trades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 1000,
):
    """Export all trades (capped at limit)."""
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).order_by(Trade.created_at.desc()).limit(limit).all()
    return {"data": [t.to_dict() for t in trades], "count": len(trades)}
