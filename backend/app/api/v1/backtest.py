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
<<<<<<< HEAD
    """Run a backtest with optional env/sector pre-filtering and comparison mode.

    Automatically loads the user's enabled risk rules and applies them
    during simulation so backtest results reflect real risk constraints.
    """
    # Load user's enabled risk rules for backtest simulation
    from app.models.risk_rule import RiskRule
    risk_rules = []
    try:
        rules = db.query(RiskRule).filter(
            RiskRule.user_id == current_user.id,
            RiskRule.is_enabled == True,
        ).all()
        risk_rules = [{"rule_type": r.rule_type, "operator": r.operator, "threshold": r.threshold}
                      for r in rules]
    except Exception:
        pass  # no risk rules configured → no constraints

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
        risk_rules=risk_rules if risk_rules else None,
    )
=======
    """Run a backtest with optional env/sector pre-filtering and comparison mode."""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测异常: {e}") from e
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

    if result.get("status") == "failed":
        raise HTTPException(status_code=400, detail=result.get("error", "回测失败"))

    # Extract the filtered result for DB storage
    filtered = result.get("filtered_result", {})
    comparison = result.get("comparison")
    unfiltered = result.get("unfiltered_result")

    symbols = result.get("symbols") or []
    start_date = result.get("start_date", "")
    end_date = result.get("end_date", "")
    strategy_type = result.get("strategy_type", "")

    def _sym_key(syms) -> tuple:
        return tuple(sorted(str(s).upper() for s in (syms or [])))

    # Collapse near-duplicates (e.g. end date in future vs today with identical metrics)
    bt = None
    recent = (
        db.query(BacktestResult)
        .filter(
            BacktestResult.user_id == current_user.id,
            BacktestResult.strategy_type == strategy_type,
            BacktestResult.start_date == start_date,
        )
        .order_by(BacktestResult.created_at.desc())
        .limit(30)
        .all()
    )
    new_ret = float(filtered.get("total_return_pct") or 0)
    new_trades = int(filtered.get("total_trades") or 0)
    new_sharpe = float(filtered.get("sharpe_ratio") or 0)
    new_key = _sym_key(symbols)
    for old in recent:
        if _sym_key(old.symbols) != new_key:
            continue
        if (
            abs(float(old.total_return_pct or 0) - new_ret) < 0.02
            and int(old.total_trades or 0) == new_trades
            and abs(float(old.sharpe_ratio or 0) - new_sharpe) < 0.02
        ):
            bt = old
            break

    if bt is None:
        bt = BacktestResult(user_id=current_user.id)
        db.add(bt)

    bt.strategy_id = req.strategy_id
    bt.strategy_name = f"{strategy_type} (筛选后)"
    bt.strategy_type = strategy_type
    bt.parameters = result.get("parameters", {})
    bt.symbols = symbols
    bt.start_date = start_date
    bt.end_date = end_date
    bt.initial_capital = result.get("initial_capital", 1000000)
    bt.final_capital = filtered.get("final_capital", 1000000)
    bt.total_return = filtered.get("total_return", 0)
    bt.total_return_pct = filtered.get("total_return_pct", 0)
    bt.annual_return = filtered.get("annual_return", 0)
    bt.max_drawdown = filtered.get("max_drawdown", 0)
    bt.max_drawdown_pct = filtered.get("max_drawdown_pct", 0)
    bt.sharpe_ratio = filtered.get("sharpe_ratio", 0)
    bt.win_rate = filtered.get("win_rate", 0)
    bt.total_trades = filtered.get("total_trades", 0)
    bt.winning_trades = filtered.get("winning_trades", 0)
    bt.losing_trades = filtered.get("losing_trades", 0)
    bt.profit_factor = filtered.get("profit_factor", 0)
    bt.equity_curve = filtered.get("equity_curve", [])
    bt.trade_records = filtered.get("trade_records", [])
    db.commit()
    db.refresh(bt)

    # Build response with full comparison data + risk stats
    response = {
        "data": bt.to_dict(),
        "filtered_result": filtered,
<<<<<<< HEAD
        "risk_rules_applied": len(risk_rules) if risk_rules else 0,
        "risk_violations": filtered.get("risk_violations", []),
        "risk_violation_count": filtered.get("risk_violation_count", 0),
=======
        "date_notes": result.get("date_notes") or filtered.get("filter_info", {}).get("date_notes") or [],
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
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
    ).order_by(BacktestResult.created_at.desc()).limit(40).all()

    # Hide near-duplicates already stored (same symbol/window metrics, different end label)
    seen = set()
    unique = []
    for r in results:
        key = (
            r.strategy_type or "",
            tuple(sorted(str(s).upper() for s in (r.symbols or []))),
            r.start_date or "",
            round(float(r.total_return_pct or 0), 2),
            int(r.total_trades or 0),
            round(float(r.sharpe_ratio or 0), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
        if len(unique) >= 20:
            break
    return {"data": [r.to_dict() for r in unique]}


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
