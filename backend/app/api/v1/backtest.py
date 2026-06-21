"""Backtest API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.backtest import BacktestResult
from app.schemas.backtest import BacktestRequest
from app.engine.backtest_engine import backtest_engine

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/run")
def run_backtest(
    req: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = backtest_engine.run(
        strategy_type=req.strategy_type,
        parameters=req.parameters,
        symbols=req.symbols,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        commission_rate=req.commission_rate,
        slippage=req.slippage,
    )

    if result["status"] == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "回测失败"))

    # Save result to database
    bt = BacktestResult(
        user_id=current_user.id,
        strategy_id=req.strategy_id,
        strategy_name=result.get("strategy_type", ""),
        strategy_type=result.get("strategy_type", ""),
        parameters=result.get("parameters", {}),
        symbols=result.get("symbols", []),
        start_date=result.get("start_date", ""),
        end_date=result.get("end_date", ""),
        initial_capital=result.get("initial_capital", 100000),
        final_capital=result.get("final_capital", 100000),
        total_return=result.get("total_return", 0),
        total_return_pct=result.get("total_return_pct", 0),
        annual_return=result.get("annual_return", 0),
        max_drawdown=result.get("max_drawdown", 0),
        max_drawdown_pct=result.get("max_drawdown_pct", 0),
        sharpe_ratio=result.get("sharpe_ratio", 0),
        win_rate=result.get("win_rate", 0),
        total_trades=result.get("total_trades", 0),
        winning_trades=result.get("winning_trades", 0),
        losing_trades=result.get("losing_trades", 0),
        profit_factor=result.get("profit_factor", 0),
        equity_curve=result.get("equity_curve", []),
        trade_records=result.get("trade_records", []),
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)

    return {"data": bt.to_dict()}


@router.get("/history")
def list_backtests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = db.query(BacktestResult).filter(
        BacktestResult.user_id == current_user.id,
    ).order_by(BacktestResult.created_at.desc()).limit(20).all()
    return {"data": [r.to_dict() for r in results]}


@router.get("/{backtest_id}")
def get_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.query(BacktestResult).filter(
        BacktestResult.id == backtest_id,
        BacktestResult.user_id == current_user.id,
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return {"data": result.to_dict()}
