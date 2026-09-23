"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.core.security import get_password_hash
from app.models.user import User
from app.models.operation_log import OperationLog
from app.models.order import Order
from app.models.position import Position
from app.models.trade import Trade
from app.models.strategy import Strategy
from app.models.backtest import BacktestResult
from app.models.notification import Notification
from app.schemas.auth import UserUpdate
from app.core.config import settings, apply_live_broker_settings, apply_llm_settings, llm_provider_snapshot
from app.engine.broker import broker_status, reset_live_broker
from app.engine.llm_engine import llm_engine
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/admin", tags=["Admin"])


class BrokerConfigUpdate(BaseModel):
    allow_live_trading: Optional[bool] = None
    broker_type: Optional[str] = Field(default=None, max_length=32)
    qmt_mini_path: Optional[str] = Field(default=None, max_length=512)
    qmt_account_id: Optional[str] = Field(default=None, max_length=64)


class LlmProviderItem(BaseModel):
    id: str
    api_key: Optional[str] = None
    clear_api_key: Optional[bool] = False
    base_url: Optional[str] = None
    model: Optional[str] = None


class LlmConfigUpdate(BaseModel):
    default_provider: Optional[str] = None
    providers: Optional[list[LlmProviderItem]] = None


class LlmTestRequest(BaseModel):
    provider: Optional[str] = None


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


@router.post("/users/{user_id}/reset-trading")
def reset_user_trading(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Clear all trading-related data for a user (fresh account state).

    Keeps user profile / role / initial_cash. Deletes strategies, orders,
    positions, trades, backtests and notifications.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Stop running strategies in executor; do NOT mutate ORM rows first
    # (bulk delete + pending UPDATE causes StaleDataError).
    try:
        from app.engine.strategy_executor import strategy_executor
        running_ids = [
            sid for (sid,) in db.query(Strategy.id).filter(
                Strategy.user_id == user_id,
                Strategy.status == "running",
            ).all()
        ]
        for sid in running_ids:
            try:
                strategy_executor.stop_strategy(sid)
            except Exception:
                pass
    except Exception:
        pass

    counts = {
        "notifications": db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False),
        "trades": db.query(Trade).filter(Trade.user_id == user_id).delete(synchronize_session=False),
        "orders": db.query(Order).filter(Order.user_id == user_id).delete(synchronize_session=False),
        "positions": db.query(Position).filter(Position.user_id == user_id).delete(synchronize_session=False),
        "backtests": db.query(BacktestResult).filter(BacktestResult.user_id == user_id).delete(synchronize_session=False),
        "strategies": db.query(Strategy).filter(Strategy.user_id == user_id).delete(synchronize_session=False),
    }

    # Reset account mode to paper; cash derives from initial_cash + empty positions/trades
    user.account_mode = "paper"

    db.add(OperationLog(
        user_id=current_user.id,
        username=current_user.username,
        action="reset_trading",
        resource=f"user:{user.username}",
        detail=(
            f"初始化账户 {user.username}(id={user_id}): "
            + ", ".join(f"{k}={v}" for k, v in counts.items())
        ),
        status="success",
    ))
    db.commit()

    return {
        "message": f"已清空用户 {user.username} 的全部交易数据",
        "data": {"user_id": user_id, "username": user.username, "cleared": counts},
    }


@router.get("/logs")
def list_logs(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    logs = db.query(OperationLog).order_by(OperationLog.created_at.desc()).limit(100).all()
    return {"data": [l.to_dict() for l in logs]}


<<<<<<< HEAD
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
=======
@router.get("/broker-config")
def get_broker_config(
    current_user: User = Depends(get_current_admin_user),
):
    """Return MiniQMT / live broker settings and soft connection status."""
    st = broker_status("live", connect=False)
    return {
        "data": {
            "allow_live_trading": settings.ALLOW_LIVE_TRADING,
            "broker_type": settings.BROKER_TYPE or "qmt",
            "qmt_mini_path": settings.QMT_MINI_PATH or "",
            "qmt_account_id": settings.QMT_ACCOUNT_ID or "",
            "status": st,
        }
    }


@router.put("/broker-config")
def update_broker_config(
    body: BrokerConfigUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Save live broker settings to .env and apply in-memory immediately."""
    data = apply_live_broker_settings(
        allow_live_trading=body.allow_live_trading,
        broker_type=body.broker_type,
        qmt_mini_path=body.qmt_mini_path,
        qmt_account_id=body.qmt_account_id,
    )
    reset_live_broker()
    st = broker_status("live", connect=False)

    db.add(OperationLog(
        user_id=current_user.id,
        username=current_user.username,
        action="update_broker_config",
        resource="broker",
        detail=(
            f"allow_live={data['allow_live_trading']}, "
            f"type={data['broker_type']}, "
            f"path={data['qmt_mini_path'] or '(empty)'}, "
            f"account={data['qmt_account_id'] or '(empty)'}"
        ),
        status="success",
    ))
    db.commit()

    return {
        "message": "实盘配置已保存（立即生效，已写入 .env）",
        "data": {**data, "status": st},
    }


@router.post("/broker-config/test")
def test_broker_connection(
    current_user: User = Depends(get_current_admin_user),
):
    """Force reconnect to MiniQMT and return live status (cash if available)."""
    reset_live_broker()
    st = broker_status("live", connect=True)
    ok = bool(st.get("connected"))
    return {
        "message": "连接成功" if ok else (st.get("message") or "连接失败"),
        "data": {"status": st},
    }


@router.get("/llm-config")
def get_llm_config(
    current_user: User = Depends(get_current_admin_user),
):
    """Return DeepSeek / GLM / Kimi API settings (keys masked)."""
    return {"data": llm_provider_snapshot(mask_keys=True)}


@router.put("/llm-config")
def update_llm_config(
    body: LlmConfigUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Save LLM provider settings to .env and apply in-memory."""
    payload = body.model_dump(exclude_unset=True)
    data = apply_llm_settings(payload)

    db.add(OperationLog(
        user_id=current_user.id,
        username=current_user.username,
        action="update_llm_config",
        resource="llm",
        detail=f"default={data.get('default_provider')}",
        status="success",
    ))
    db.commit()
    return {"message": "大模型配置已保存（立即生效，已写入 .env）", "data": data}


@router.post("/llm-config/test")
def test_llm_connection(
    body: LlmTestRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """Ping selected LLM provider with a tiny chat request."""
    result = llm_engine.test_connection(body.provider)
    return {
        "message": result.get("message") or ("连接成功" if result.get("ok") else "连接失败"),
        "data": result,
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    }
