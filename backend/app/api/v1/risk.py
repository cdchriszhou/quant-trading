"""Risk control API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.risk_rule import RiskRule
from app.schemas.risk import RiskRuleCreate, RiskRuleUpdate, RiskCheckRequest
from app.engine.risk_engine import risk_engine

router = APIRouter(prefix="/risk", tags=["Risk Control"])


@router.get("/rules")
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rules = db.query(RiskRule).filter(RiskRule.user_id == current_user.id).all()
    return {"data": [r.to_dict() for r in rules]}


@router.post("/rules")
def create_rule(
    req: RiskRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = RiskRule(
        user_id=current_user.id,
        name=req.name,
        rule_type=req.rule_type,
        operator=req.operator,
        threshold=req.threshold,
        action=req.action,
        description=req.description,
        is_enabled=req.is_enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"data": rule.to_dict()}


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    req: RiskRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(RiskRule).filter(
        RiskRule.id == rule_id,
        RiskRule.user_id == current_user.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    if req.name is not None:
        rule.name = req.name
    if req.rule_type is not None:
        rule.rule_type = req.rule_type
    if req.operator is not None:
        rule.operator = req.operator
    if req.threshold is not None:
        rule.threshold = req.threshold
    if req.action is not None:
        rule.action = req.action
    if req.description is not None:
        rule.description = req.description
    if req.is_enabled is not None:
        rule.is_enabled = req.is_enabled

    db.commit()
    db.refresh(rule)
    return {"data": rule.to_dict()}


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(RiskRule).filter(
        RiskRule.id == rule_id,
        RiskRule.user_id == current_user.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
    return {"message": "规则已删除"}


@router.post("/check")
def check_order_risk(
    req: RiskCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = risk_engine.check_order(
        db, current_user.id, req.symbol, req.side,
        req.quantity, req.price, req.amount
    )
    return result
