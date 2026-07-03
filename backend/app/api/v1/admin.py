"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

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


@router.post("/reset")
def reset_system(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """重置系统 — 删除所有策略、订单、持仓、交易记录（保留用户账户）。

    清空表: strategies, orders, positions, trades, operation_logs,
           backtest_results, notifications, market_env_records,
           sector_rankings, risk_rules
    使用 TRUNCATE 语句高效清空，并重置自增 ID。
    """
    # Tables to truncate (order matters for FK constraints — child tables first)
    tables = [
        "operation_logs",
        "notifications",
        "sector_rankings",
        "market_env_records",
        "backtest_results",
        "trades",
        "orders",
        "positions",
        "strategies",
        "risk_rules",
    ]

    deleted_counts = {}
    try:
        for table_name in tables:
            # Count before truncate
            count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            deleted_counts[table_name] = count or 0
            # TRUNCATE is faster and resets auto-increment
            db.execute(text(f"DELETE FROM {table_name}"))

        db.commit()

        # Reset auto-increment counters for SQLite (DELETE doesn't reset them)
        for table_name in tables:
            try:
                db.execute(text(
                    f"UPDATE sqlite_sequence SET seq=0 WHERE name='{table_name}'"
                ))
            except Exception:
                pass  # MySQL doesn't have sqlite_sequence, ignore
        db.commit()

        return {
            "message": "系统已重置",
            "deleted": deleted_counts,
            "total_deleted": sum(deleted_counts.values()),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")


@router.get("/broker")
def get_broker_status(
    current_user: User = Depends(get_current_admin_user),
):
    """获取当前券商连接状态（管理员可见）。"""
    from app.brokers import get_broker

    broker = get_broker()
    state = broker.get_state()

    return {
        "data": {
            "broker_type": state.broker_type,
            "connection": state.connection.value,
            "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
            "error_message": state.error_message,
        }
    }


@router.post("/broker/reconnect")
async def reconnect_broker(
    current_user: User = Depends(get_current_admin_user),
):
    """重新连接券商（管理员操作）。"""
    from app.brokers import get_broker

    broker = get_broker()
    await broker.disconnect()
    state = await broker.connect()

    return {
        "message": f"已重新连接: {state.broker_type}",
        "broker_type": state.broker_type,
        "connection": state.connection.value,
    }
