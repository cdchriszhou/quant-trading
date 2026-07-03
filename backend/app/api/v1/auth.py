"""Auth API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.models.operation_log import OperationLog
from app.schemas.auth import LoginRequest, RegisterRequest, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _log_operation(db: Session, user_id: int, username: str, action: str,
                   resource: str = "", detail: str = "", ip: str = ""):
    log = OperationLog(
        user_id=user_id, username=username, action=action,
        resource=resource, detail=detail, ip_address=ip,
    )
    db.add(log)
    db.commit()


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已禁用")

    token = create_access_token({"sub": user.username, "role": user.role})
    user.last_login = datetime.utcnow()
    db.commit()

    _log_operation(db, user.id, user.username, "login", detail="用户登录", ip="")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=request.username,
        hashed_password=get_password_hash(request.password),
        email=request.email,
        display_name=request.display_name or request.username,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {"user": current_user.to_dict()}


@router.put("/profile")
def update_profile(
    update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if update.email is not None:
        user.email = update.email
    if update.display_name is not None:
        user.display_name = update.display_name
    if update.password is not None:
        user.hashed_password = get_password_hash(update.password)
    db.commit()
    db.refresh(user)
    return {"user": user.to_dict()}
