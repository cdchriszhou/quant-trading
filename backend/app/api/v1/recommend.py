"""Stock recommendation API — capital-matched short-hold candidates."""

import asyncio

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import llm_provider_snapshot
from app.models.user import User
from app.engine.trading_engine import trading_engine
from app.engine.recommend_engine import recommend_engine

router = APIRouter(prefix="/recommend", tags=["Recommendations"])


@router.get("/llm-options")
def llm_options(current_user: User = Depends(get_current_user)):
    """Providers available for optional LLM fusion (no secrets)."""
    snap = llm_provider_snapshot(mask_keys=True)
    providers = [
        {
            "id": p["id"],
            "name": p["name"],
            "configured": p["configured"],
            "model": p["model"],
        }
        for p in snap.get("providers") or []
    ]
    return {
        "data": {
            "default_provider": snap.get("default_provider"),
            "any_configured": any(p["configured"] for p in providers),
            "providers": providers,
        }
    }


@router.get("/short-hold")
async def short_hold_recommendations(
    max_results: int = Query(8, ge=3, le=20),
    max_position_pct: float = Query(0.25, ge=0.05, le=1.0),
    budget_amount: Optional[float] = Query(
        None, ge=0, description="单票固定预算金额；上限为总资产"
    ),
    hold_days: int = Query(7, ge=3, le=20),
    min_rr: float = Query(1.5, ge=1.0, le=5.0),
    refresh: bool = Query(False, description="跳过服务端结果缓存，强制重算"),
    use_llm: bool = Query(False, description="启用多模型融合参考（不改变硬过滤）"),
    llm_providers: Optional[str] = Query(
        None,
        description="逗号分隔：deepseek,glm,kimi,qwen；空则用全部已配置模型",
    ),
    llm_provider: Optional[str] = Query(
        None, description="兼容旧参数；可与 llm_providers 同义"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recommend stocks sized to current available cash for short-term holds.

    Does not guarantee profit — filters by trend, liquidity, risk/reward,
    and whether at least one lot fits the cash budget.
    """
    summary = trading_engine.get_account_summary(db, current_user.id)
    cash = float(summary.get("cash_balance") or 0)
    total_equity = float(summary.get("total_equity") or cash)

    if budget_amount is not None and budget_amount > total_equity + 1e-6:
        raise HTTPException(
            status_code=400,
            detail=f"单票金额不能超过总资产 ¥{total_equity:,.2f}",
        )

    provider_list = None
    raw = (llm_providers or llm_provider or "").strip()
    if raw:
        provider_list = [p.strip() for p in raw.split(",") if p.strip()]

    data = await asyncio.to_thread(
        recommend_engine.recommend,
        cash,
        total_equity=total_equity,
        max_position_pct=max_position_pct,
        budget_amount=budget_amount,
        max_results=max_results,
        hold_days_hint=hold_days,
        min_rr=min_rr,
        use_cache=not refresh and not use_llm,
        use_llm=use_llm,
        llm_providers=provider_list,
    )
    data["account_mode"] = summary.get("account_mode") or trading_engine.get_user_mode(
        db, current_user.id
    )
    data["market_value"] = summary.get("market_value")
    return {"data": data}
