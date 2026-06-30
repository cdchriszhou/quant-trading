"""Backtest API routes — supports multi-layer pre-filtering and comparison."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.backtest import BacktestResult
from app.schemas.backtest import BacktestRequest, BacktestOptimizeRequest
from app.engine.backtest_engine import backtest_engine

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/run")
def run_backtest(
    req: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run a backtest with optional env/sector pre-filtering and comparison mode."""
    result = backtest_engine.run(
        strategy_type=req.strategy_type,
        parameters=req.parameters,
        symbols=req.symbols,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        commission_rate=req.commission_rate,
        slippage=req.slippage,
        enable_env_filter=req.enable_env_filter,
        enable_sector_filter=req.enable_sector_filter,
        comparison_mode=req.comparison_mode,
    )

    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "回测失败"))

    # Extract the filtered result for DB storage
    filtered = result.get("filtered_result", {})
    comparison = result.get("comparison")
    unfiltered = result.get("unfiltered_result")

    # Save result to database
    bt = BacktestResult(
        user_id=current_user.id,
        strategy_id=req.strategy_id,
        strategy_name=f"{result.get('strategy_type', '')} (筛选后)",
        strategy_type=result.get("strategy_type", ""),
        parameters=result.get("parameters", {}),
        symbols=result.get("symbols", []),
        start_date=result.get("start_date", ""),
        end_date=result.get("end_date", ""),
        initial_capital=result.get("initial_capital", 100000),
        final_capital=filtered.get("final_capital", 100000),
        total_return=filtered.get("total_return", 0),
        total_return_pct=filtered.get("total_return_pct", 0),
        annual_return=filtered.get("annual_return", 0),
        max_drawdown=filtered.get("max_drawdown", 0),
        max_drawdown_pct=filtered.get("max_drawdown_pct", 0),
        sharpe_ratio=filtered.get("sharpe_ratio", 0),
        win_rate=filtered.get("win_rate", 0),
        total_trades=filtered.get("total_trades", 0),
        winning_trades=filtered.get("winning_trades", 0),
        losing_trades=filtered.get("losing_trades", 0),
        profit_factor=filtered.get("profit_factor", 0),
        equity_curve=filtered.get("equity_curve", []),
        trade_records=filtered.get("trade_records", []),
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)

    # Build response with full comparison data
    response = {
        "data": bt.to_dict(),
        "filtered_result": filtered,
    }
    if unfiltered:
        response["unfiltered_result"] = unfiltered
    if comparison:
        response["comparison"] = comparison

    return response


@router.post("/optimize")
def optimize_backtest(
    req: BacktestOptimizeRequest,
    current_user: User = Depends(get_current_user),
):
    """Auto-optimize strategy parameters to find the most stable combination."""
    try:
        result = backtest_engine.optimize(
            strategy_type=req.strategy_type,
            base_parameters=req.base_parameters,
            symbols=req.symbols,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            enable_env_filter=req.enable_env_filter,
            enable_sector_filter=req.enable_sector_filter,
        )
        return {"data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"参数优化失败: {e}")


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
