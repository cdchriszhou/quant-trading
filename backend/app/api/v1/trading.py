"""Trading API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.trading import OrderCreate, OrderCancel
from app.engine.trading_engine import trading_engine, TradingEngineError
from app.engine.risk_engine import risk_engine
from app.engine.data_engine import data_engine
from app.engine.fee_engine import fee_engine
from app.engine.broker import broker_status

router = APIRouter(prefix="/trading", tags=["Trading"])


class AccountModeRequest(BaseModel):
    mode: str  # paper | live


class SimulatedCashRequest(BaseModel):
    initial_cash: float


@router.get("/account-mode")
def get_account_mode(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    mode = getattr(user, "account_mode", None) or "paper"
    return {
        "data": {
            "mode": mode,
            "allow_live": settings.ALLOW_LIVE_TRADING,
            "broker_type": settings.BROKER_TYPE,
            "broker": broker_status(mode, connect=False),
            "fee_rates": {
                "commission_rate": settings.COMMISSION_RATE,
                "min_commission": settings.MIN_COMMISSION,
                "stamp_duty_rate": settings.STAMP_DUTY_RATE,
                "transfer_fee_rate": settings.TRANSFER_FEE_RATE,
            },
            "data_policy": "行情/K线/板块均为真实数据；仅资金可在模拟账本与真实券商账户间切换",
        }
    }


@router.put("/account-mode")
def set_account_mode(
    req: AccountModeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="mode 仅支持 paper / live")
    if req.mode == "live" and not settings.ALLOW_LIVE_TRADING:
        raise HTTPException(
            status_code=400,
            detail="实盘未启用：请在后端 .env 设置 ALLOW_LIVE_TRADING=true 并配置 MiniQMT",
        )
    if req.mode == "live":
        st = broker_status("live", connect=True)
        if not st.get("connected"):
            raise HTTPException(
                status_code=400,
                detail=f"无法切换实盘：{st.get('message') or '券商未连接'}（请到系统管理→实盘接入检查）",
            )

    user = db.query(User).filter(User.id == current_user.id).first()
    user.account_mode = req.mode
    db.commit()
    return {
        "data": {
            "mode": user.account_mode,
            "broker": broker_status(user.account_mode, connect=False),
        },
        "message": "已切换为模拟资金" if req.mode == "paper" else "已切换为真实券商账户",
    }


@router.put("/simulated-cash")
def set_simulated_cash(
    req: SimulatedCashRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.initial_cash < 1000:
        raise HTTPException(status_code=400, detail="模拟资金至少 1000")
    user = db.query(User).filter(User.id == current_user.id).first()
    user.initial_cash = float(req.initial_cash)
    db.commit()
    return {"data": {"initial_cash": user.initial_cash}, "message": "模拟初始资金已更新"}


@router.get("/fee-preview")
def fee_preview(
    side: str = Query("buy"),
    price: float = Query(...),
    quantity: float = Query(...),
    current_user: User = Depends(get_current_user),
):
    return {"data": fee_engine.calculate(side, price, quantity).to_dict()}


@router.post("/orders")
def place_order(
    req: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order_price = req.price
    if order_price is None or order_price <= 0:
        try:
            quote = data_engine.get_realtime_quote(req.symbol)
            order_price = float(quote.get("current_price") or 0)
        except Exception:
            order_price = 0
    if order_price <= 0:
        raise HTTPException(status_code=400, detail="无法获取真实报价")

    amount = req.quantity * order_price
    if req.side == "buy":
        amount = fee_engine.buy_cost(order_price, req.quantity)
    risk_result = risk_engine.check_order(
        db, current_user.id, req.symbol, req.side, req.quantity,
        order_price, amount,
    )
    if risk_result.get("should_pause"):
        return {
            "status": "rejected",
            "message": "触发暂停策略风控，订单已拦截",
            "violations": risk_result["violations"],
            "warnings": risk_result.get("warnings", []),
        }
    if not risk_result["passed"]:
        return {
            "status": "rejected",
            "message": "风控规则未通过",
            "violations": risk_result["violations"],
            "warnings": risk_result.get("warnings", []),
        }

    # Prefer user account_mode; allow explicit override from form
    mode = req.mode or trading_engine.get_user_mode(db, current_user.id)
    account_mode = trading_engine.get_user_mode(db, current_user.id)
    if mode == "live" and account_mode != "live":
        raise HTTPException(
            status_code=400,
            detail="账户为模拟模式时不能下实盘单。请先切换账户到「实盘」",
        )
    if req.strategy_id is not None:
        from app.models.strategy import Strategy
        owned = db.query(Strategy).filter(
            Strategy.id == req.strategy_id,
            Strategy.user_id == current_user.id,
        ).first()
        if not owned:
            raise HTTPException(status_code=404, detail="策略不存在或不属于当前用户")

    try:
        order = trading_engine.place_order(
            db, current_user.id, req.symbol, req.side, req.order_type,
            req.quantity, order_price if req.order_type == "market" else req.price,
            req.strategy_id, req.remark or "",
            mode_override=mode,
        )
    except TradingEngineError as e:
        return {
            "status": "rejected",
            "message": str(e),
            "violations": [],
            "fee_preview": fee_engine.calculate(req.side, order_price, req.quantity).to_dict(),
        }

    result = {
        "data": order.to_dict(),
        "fee_preview": fee_engine.calculate(req.side, order_price, req.quantity).to_dict(),
    }
    if risk_result.get("warnings"):
        result["warnings"] = risk_result["warnings"]
    return result


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
    try:
        order = trading_engine.cancel_order(db, order_id, current_user.id)
    except TradingEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


@router.get("/equity-curve")
def get_equity_curve(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"data": trading_engine.get_equity_curve(db, current_user.id)}
