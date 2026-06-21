"""Strategy management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate
from app.engine.strategy_engine import strategy_engine

router = APIRouter(prefix="/strategies", tags=["Strategies"])


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
    strategy = Strategy(
        user_id=current_user.id,
        name=req.name,
        description=req.description,
        strategy_type=req.strategy_type,
        asset_type=req.asset_type,
        symbols=req.symbols,
        parameters=req.parameters or strategy_engine.get_default_params(req.strategy_type),
        time_frame=req.time_frame,
        mode=req.mode,
        initial_capital=req.initial_capital,
        current_capital=req.initial_capital,
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
    if req.status is not None:
        strategy.status = req.status

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
    strategy.status = "running"
    db.commit()
    return {"data": strategy.to_dict()}


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
    return {"data": strategy.to_dict()}
