"""Trading API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.trading import OrderCreate, OrderCancel
from app.engine.trading_engine import trading_engine
from app.engine.risk_engine import risk_engine

router = APIRouter(prefix="/trading", tags=["Trading"])


@router.post("/orders")
def place_order(
    req: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Risk check
    risk_result = risk_engine.check_order(
        db, current_user.id, req.symbol, req.side, req.quantity,
        req.price or 0, req.quantity * (req.price or 1)
    )
    if not risk_result["passed"]:
        return {
            "status": "rejected",
            "message": "风控规则未通过",
            "violations": risk_result["violations"],
        }

    order = trading_engine.place_order(
        db, current_user.id, req.symbol, req.side, req.order_type,
        req.quantity, req.price, req.strategy_id, req.remark or "",
        mode_override=req.mode,
    )
    return {"data": order.to_dict()}


@router.get("/orders")
def list_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = trading_engine.get_orders(db, current_user.id, status, limit)
    return {"data": orders}


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = trading_engine.cancel_order(db, order_id, current_user.id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或已处理")
    return {"data": order.to_dict()}


@router.get("/positions")
def list_positions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    positions = trading_engine.get_positions(db, current_user.id)
    return {"data": positions}


@router.get("/account")
def get_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    summary = trading_engine.get_account_summary(db, current_user.id)
    return {"data": summary}
