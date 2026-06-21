"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.core.security import get_password_hash
from app.models.user import User
from app.models.operation_log import OperationLog
from app.schemas.auth import UserUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    return {"data": [u.to_dict() for u in users]}


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if update.role is not None:
        user.role = update.role
    if update.is_active is not None:
        user.is_active = update.is_active
    if update.initial_cash is not None:
        user.initial_cash = update.initial_cash
    if update.password is not None:
        user.hashed_password = get_password_hash(update.password)

    db.commit()
    db.refresh(user)
    return {"data": user.to_dict()}


@router.get("/logs")
def list_logs(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    logs = db.query(OperationLog).order_by(OperationLog.created_at.desc()).limit(100).all()
    return {"data": [l.to_dict() for l in logs]}
