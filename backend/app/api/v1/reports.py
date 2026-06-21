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

    today_trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).count()

    recent_trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).order_by(Trade.created_at.desc()).limit(10).all()

    overview = data_engine.get_market_overview()

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
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).all()

    total_trades = len(trades)
    buy_trades = len([t for t in trades if t.side == "buy"])
    sell_trades = len([t for t in trades if t.side == "sell"])
    total_commission = sum(t.commission for t in trades)
    total_pnl = sum(t.pnl for t in trades if t.pnl)

    winning_trades = len([t for t in trades if t.pnl and t.pnl > 0])
    losing_trades = len([t for t in trades if t.pnl and t.pnl < 0])
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
):
    trades = db.query(Trade).filter(
        Trade.user_id == current_user.id,
    ).order_by(Trade.created_at.desc()).all()
    return {"data": [t.to_dict() for t in trades]}
