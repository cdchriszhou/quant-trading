"""Strategy management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate
from app.engine.strategy_engine import strategy_engine
from app.engine.strategy_executor import strategy_executor
from app.engine.broker import broker_status

router = APIRouter(prefix="/strategies", tags=["Strategies"])


def _require_live_ready() -> None:
    """Raise if live trading is not enabled or broker is disconnected."""
    if not settings.ALLOW_LIVE_TRADING:
        raise HTTPException(
            status_code=400,
            detail="实盘未启用：请在后端 .env 设置 ALLOW_LIVE_TRADING=true 并配置 MiniQMT",
        )
    st = broker_status("live")
    if not st.get("connected"):
        raise HTTPException(
            status_code=400,
            detail=f"实盘通道未就绪：{st.get('message') or '请配置 QMT_MINI_PATH / QMT_ACCOUNT_ID'}",
        )


@router.get("/types")
def get_strategy_types():
    return {"data": strategy_engine.get_supported_strategies()}


@router.get("/default-params/{strategy_type}")
def get_default_params(strategy_type: str):
    return {"params": strategy_engine.get_default_params(strategy_type)}


@router.get("")
def list_strategies(
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Strategy).filter(Strategy.user_id == current_user.id)
    if status:
        query = query.filter(Strategy.status == status)
    strategies = query.order_by(Strategy.created_at.desc()).all()
    return {"data": [s.to_dict() for s in strategies]}


@router.post("")
def create_strategy(
    req: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
<<<<<<< HEAD
    # Auto-set initial_capital: use user's remaining cash if not explicitly provided
    from app.models.trade import Trade
    from sqlalchemy import func, case

    if req.initial_capital and req.initial_capital > 0:
        initial_capital = req.initial_capital
    else:
        # Calculate remaining cash: initial_cash - bought + sold
        agg = db.query(
            func.coalesce(
                func.sum(case((Trade.side == "buy", Trade.amount + Trade.commission), else_=0)), 0
            ).label("total_bought"),
            func.coalesce(
                func.sum(case((Trade.side == "sell", Trade.amount - Trade.commission), else_=0)), 0
            ).label("total_sold"),
        ).filter(Trade.user_id == current_user.id).first()

        total_bought = float(agg.total_bought)
        total_sold = float(agg.total_sold)
        initial_capital = max(
            current_user.initial_cash - total_bought + total_sold,
            10000,  # minimum 1万
        )

=======
    mode = req.mode if req.mode in ("paper", "live") else "paper"
    if mode == "live":
        _require_live_ready()
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    strategy = Strategy(
        user_id=current_user.id,
        name=req.name,
        description=req.description,
        strategy_type=req.strategy_type,
        asset_type=req.asset_type,
        symbols=req.symbols,
        parameters=req.parameters or strategy_engine.get_default_params(req.strategy_type),
        time_frame=req.time_frame,
<<<<<<< HEAD
        mode=req.mode,
        initial_capital=round(initial_capital, 2),
        current_capital=round(initial_capital, 2),
=======
        mode=mode,
        initial_capital=req.initial_capital,
        current_capital=req.initial_capital,
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return {"data": strategy.to_dict()}


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"data": strategy.to_dict()}


@router.put("/{strategy_id}")
def update_strategy(
    strategy_id: int,
    req: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    if req.name is not None:
        strategy.name = req.name
    if req.description is not None:
        strategy.description = req.description
    if req.parameters is not None:
        strategy.parameters = req.parameters
    if req.symbols is not None:
        strategy.symbols = req.symbols
    if req.time_frame is not None:
        strategy.time_frame = req.time_frame
    if req.initial_capital is not None:
        strategy.initial_capital = req.initial_capital
    # status must go through /start or /stop (live broker checks + executor lifecycle)
    if req.status is not None and req.status != strategy.status:
        raise HTTPException(
            status_code=400,
            detail="请使用「启动/停止」接口变更运行状态，勿直接修改 status",
        )

    db.commit()
    db.refresh(strategy)
    return {"data": strategy.to_dict()}


@router.delete("/{strategy_id}")
def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    db.delete(strategy)
    db.commit()
    return {"message": "策略已删除"}


@router.post("/{strategy_id}/start")
def start_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.mode == "live":
        _require_live_ready()
        # Prevent UI showing paper equity while auto-orders hit the real broker
        if (current_user.account_mode or "paper") != "live":
            raise HTTPException(
                status_code=400,
                detail="账户当前为模拟模式。请先在交易账户切换到「实盘」再启动实盘策略",
            )
    strategy.status = "running"
    db.commit()
    db.refresh(strategy)
    # Start background execution
    strategy_executor.start_strategy(strategy.id)
    return {"data": strategy.to_dict(), "message": "策略已启动"}


@router.post("/{strategy_id}/stop")
def stop_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id,
    ).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    strategy.status = "stopped"
    db.commit()
    db.refresh(strategy)
    # Stop background execution
    strategy_executor.stop_strategy(strategy.id)
    return {"data": strategy.to_dict(), "message": "策略已停止"}
