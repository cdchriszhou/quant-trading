"""Pre-launch logic smoke checks (no external UI). Exit 0 = pass."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

sys.path.insert(0, ".")

FAILS: list[str] = []
WARNS: list[str] = []


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str, exc: Exception | None = None) -> None:
    FAILS.append(msg)
    print(f" FAIL {msg}")
    if exc:
        print(f"      {type(exc).__name__}: {exc}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f" WARN {msg}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_imports() -> None:
    section("Imports")
    mods = [
        "app.main",
        "app.engine.market_env_engine",
        "app.engine.market_forecast_engine",
        "app.engine.recommend_engine",
        "app.engine.strategy_executor",
        "app.engine.strategy_engine",
        "app.engine.notification_engine",
        "app.engine.data_engine",
        "app.engine.sector_engine",
        "app.schemas.notification",
        "app.api.v1.notifications",
        "app.api.v1.market",
        "app.api.v1.trading",
    ]
    for m in mods:
        try:
            __import__(m)
            ok(m)
        except Exception as e:
            fail(f"import {m}", e)


def check_notification_schema() -> None:
    section("Notification schema")
    from app.schemas.notification import NotificationOut, NotificationListOut, MarkReadRequest

    class Obj:
        id = 1
        user_id = 1
        type = "system"
        title = "测试"
        message = "hello"
        strategy_id = None
        strategy_name = None
        order_id = None
        symbol = None
        price = None
        is_read = False
        created_at = datetime.now()

    try:
        out = NotificationOut.model_validate(Obj())
        assert isinstance(out.created_at, str) and out.created_at
        ok(f"NotificationOut datetime→str ({out.created_at})")
    except Exception as e:
        fail("NotificationOut validation", e)

    try:
        from app.models.notification import Notification
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            n = db.query(Notification).order_by(Notification.id.desc()).first()
            unread = db.query(Notification).filter(Notification.is_read == False).count()  # noqa: E712
            total = db.query(Notification).count()
            ok(f"DB notifications total={total} unread={unread}")
            if n:
                raw = n.to_dict()
                NotificationOut.model_validate(raw)
                NotificationOut.model_validate(n)
                ok(f"ORM+to_dict validate id={n.id}")
            else:
                warn("no notification rows yet (list page will be empty until events fire)")
        finally:
            db.close()
    except Exception as e:
        fail("notification DB read", e)

    try:
        MarkReadRequest(ids=None)
        MarkReadRequest(ids=[])
        MarkReadRequest(ids=[1, 2])
        ok("MarkReadRequest variants")
        NotificationListOut(items=[], total=0, unread_count=0)
        ok("NotificationListOut empty")
    except Exception as e:
        fail("notification request/list schemas", e)


def check_env_forecast() -> None:
    section("Market env + forecast")
    from app.engine.market_env_engine import market_env_engine
    from app.engine.market_forecast_engine import market_forecast_engine

    try:
        env = market_env_engine.check_environment()
        required = ["env_state", "can_trade", "exposure_mult", "message", "checklist"]
        missing = [k for k in required if k not in env]
        if missing:
            fail(f"env missing keys {missing}")
        else:
            ok(
                f"env state={env.get('env_state')} can_trade={env.get('can_trade')} "
                f"exp={env.get('exposure_mult')} days_below={env.get('days_below_ma20')}"
            )
        # Logic: if tape bullish, should not hard-lock as bear with 0 exposure
        cl = env.get("checklist") or {}
        idx = env.get("index_bias")
        br = env.get("breadth_bias")
        if (idx == "bull" or br == "bull") and env.get("env_state") == "bear" and not env.get("can_trade"):
            fail("env: tape alive but labeled bear + can_trade=False (recommend/executor freeze risk)")
        elif env.get("env_state") == "bear" and env.get("can_trade"):
            warn("env: bear but can_trade=True (unexpected combo)")
        else:
            ok(f"env tape consistency index={idx} breadth={br}")
        if cl.get("shallow_pullback") and env.get("env_state") == "bear":
            fail("shallow_pullback should not be structural bear")
    except Exception as e:
        fail("check_environment", e)
        return

    try:
        fc = market_forecast_engine.forecast(horizon_days=5)
        for k in ("forecast_score", "exposure_mult", "horizon_bias", "zone"):
            if k not in fc:
                fail(f"forecast missing {k}")
        score = float(fc.get("forecast_score") or 0)
        if not (0 <= score <= 100):
            fail(f"forecast_score out of range: {score}")
        else:
            ok(f"forecast score={score} bias={fc.get('horizon_bias')} exp={fc.get('exposure_mult')}")
    except Exception as e:
        fail("forecast", e)


def check_recommend() -> None:
    section("Recommend engine")
    from app.engine.recommend_engine import recommend_engine

    try:
        rec = recommend_engine.recommend(
            cash=100000,
            total_equity=100000,
            max_position_pct=0.25,
            max_results=8,
            use_cache=False,
            universe_limit=60,
        )
    except Exception as e:
        fail("recommend()", e)
        return

    policy = rec.get("open_policy")
    size = float(rec.get("size_mult") or 0)
    budget = float(rec.get("budget_per_name") or 0)
    items = rec.get("recommendations") or []
    stats = rec.get("scan_stats") or {}
    ok(f"policy={policy} size_mult={size:.3f} budget={budget:.0f} n={len(items)}")
    ok(f"scan={stats}")

    if size < 0.35:
        fail(f"size_mult too small ({size}) — tickets may be unbuyable")
    if budget > 0 and budget < 3000:
        warn(f"budget_per_name very low ({budget:.0f})")

    # env pause must not zero recommend sizing
    env = rec.get("market_env") or {}
    if env.get("can_trade") is False and size < 0.35:
        fail("executor pause collapsed recommend size_mult")

    bares = set()
    for it in items:
        sym = it.get("symbol") or ""
        bare = sym.split(".")[0]
        if bare in bares:
            fail(f"duplicate bare symbol in recommendations: {sym}")
        bares.add(bare)
        setup = it.get("setup_type")
        if setup not in ("trend_pullback", "dip_bounce", "rs_hold"):
            fail(f"unknown setup_type {setup} on {sym}")
        score = float(it.get("score") or 0)
        if score <= 0:
            fail(f"non-positive score on {sym}")
        rr = float(it.get("risk_reward") or 0)
        if rr < 1.0:
            fail(f"RR < 1 on {sym}: {rr}")
        for k in ("stop_loss", "take_profit", "suggested_quantity", "reasons"):
            if it.get(k) in (None, "", []):
                fail(f"missing {k} on {sym}")
    if items:
        ok(f"recommendation fields unique={len(bares)} setups ok")
    else:
        warn("recommend returned 0 items (may be ok if market empty)")

    # allow_rs / allow_dip flags present
    for k in ("allow_dip", "allow_rs", "open_policy", "quality_policy"):
        if k not in rec:
            fail(f"recommend meta missing {k}")


def check_strategies_signals() -> None:
    section("Strategy signals (sample symbols)")
    import datetime as dt
    from app.engine.data_engine import data_engine
    from app.engine.strategy_engine import strategy_engine

    end = dt.datetime.now().strftime("%Y-%m-%d")
    start = (dt.datetime.now() - dt.timedelta(days=280)).strftime("%Y-%m-%d")
    samples = [
        ("000001.SZ", "dragon_pullback"),
        ("000001.SZ", "right_side_entry"),
        ("600519.SH", "right_side_entry"),
    ]
    for sym, stype in samples:
        try:
            df = data_engine.get_history_data(sym, start, end)
            if df is None or getattr(df, "empty", True) or len(df) < 60:
                warn(f"{sym} history thin for {stype}")
                continue
            sig = strategy_engine.calculate_signals(stype, df, {})
            last = sig.iloc[-1]
            assert "buy_signal" in sig.columns and "sell_signal" in sig.columns
            ok(
                f"{stype}@{sym} buy={bool(last.get('buy_signal'))} "
                f"sell={bool(last.get('sell_signal'))} bars={len(sig)}"
            )
        except Exception as e:
            fail(f"signals {stype}@{sym}", e)


def check_kline_quote() -> None:
    section("Kline + quote")
    from app.engine.data_engine import data_engine

    for sym in ("600519.SH", "000001.SZ"):
        try:
            kl = data_engine.get_kline_data(sym, "1d", 10)
            if not kl or len(kl) < 3:
                fail(f"kline empty {sym}")
            else:
                ok(f"kline {sym} n={len(kl)} last={kl[-1].get('date')}")
        except Exception as e:
            fail(f"kline {sym}", e)
        try:
            q = data_engine.get_realtime_quote(sym)
            px = float(q.get("current_price") or 0)
            if px <= 0:
                fail(f"quote bad price {sym}: {q}")
            else:
                ok(f"quote {sym} px={px}")
        except Exception as e:
            fail(f"quote {sym}", e)

    try:
        movers = data_engine.get_top_movers(10, "main") or {}
        g = movers.get("gainers") or []
        boards = {data_engine._market_board(x.get("code") or "") for x in g}
        if g and boards == {"bse"}:
            fail("top movers main board returned only BSE")
        else:
            ok(f"top movers main n={len(g)} boards={boards or '-'}")
    except Exception as e:
        fail("top movers", e)


def check_executor_env_gate_logic() -> None:
    section("Executor env-gate contract")
    # Static expectations vs live env — no live order placement
    from app.engine.market_env_engine import market_env_engine

    env = market_env_engine.check_environment()
    exp = float(env.get("exposure_mult") if env.get("exposure_mult") is not None else 0)
    can = bool(env.get("can_trade"))
    state = env.get("env_state")

    # Document expected executor behavior
    if state == "bear" or not can or exp < 0.15:
        ok(f"executor would LOCK buys (state={state} can={can} exp={exp})")
    else:
        ok(f"executor would ALLOW buys with size×{exp} (state={state})")

    # Recommend must stay available when executor locks
    from app.engine.recommend_engine import recommend_engine

    rec = recommend_engine.recommend(
        cash=50000, total_equity=50000, max_position_pct=0.3,
        max_results=5, use_cache=False, universe_limit=40,
    )
    if not can and float(rec.get("size_mult") or 0) >= 0.35:
        ok("recommend still sized when executor paused")
    elif can:
        ok("executor open; recommend sizing independent check skipped")
    else:
        fail("recommend size collapsed while executor paused")


def check_router_and_frontend_paths() -> None:
    section("Frontend route/file presence")
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    need = [
        "views/system/Notifications.vue",
        "layouts/SidebarMenu.vue",
        "layouts/MainLayout.vue",
        "views/market/Index.vue",
        "views/recommend/Index.vue",
        "router/index.js",
    ]
    for rel in need:
        p = root / rel
        if not p.exists():
            fail(f"missing {rel}")
        else:
            ok(rel)

    router = (root / "router" / "index.js").read_text(encoding="utf-8")
    if "notifications" not in router:
        fail("router missing notifications path")
    else:
        ok("router has /notifications")

    side = (root / "layouts" / "SidebarMenu.vue").read_text(encoding="utf-8")
    if "teleport" not in side.lower():
        warn("SidebarMenu may not teleport flyout (collapse overflow risk)")
    else:
        ok("SidebarMenu uses teleport flyout")


def main() -> int:
    print("Pre-launch check", datetime.now().isoformat(timespec="seconds"))
    check_imports()
    check_notification_schema()
    check_env_forecast()
    check_kline_quote()
    check_strategies_signals()
    check_recommend()
    check_executor_env_gate_logic()
    check_router_and_frontend_paths()

    print("\n=== SUMMARY ===")
    print(f"fails={len(FAILS)} warns={len(WARNS)}")
    for f in FAILS:
        print(f"  - FAIL: {f}")
    for w in WARNS:
        print(f"  - WARN: {w}")
    if FAILS:
        print("RESULT: BLOCKED")
        return 1
    print("RESULT: PASS" + (" (with warnings)" if WARNS else ""))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
