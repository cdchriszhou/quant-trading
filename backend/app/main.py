"""Quant Trading System — FastAPI Application Entry Point."""

import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.api.v1 import auth, market, strategy_api, trading, backtest, risk, reports, admin, notifications, env, sector, recommend
from app.engine.data_engine import data_engine
from app.engine.strategy_executor import strategy_executor
from app.engine.notification_engine import notification_engine
from app.core.security import decode_access_token

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(strategy_api.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(env.router, prefix="/api/v1")
app.include_router(sector.router, prefix="/api/v1")
app.include_router(recommend.router, prefix="/api/v1")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()


@app.websocket("/ws/market")
<<<<<<< HEAD
async def websocket_market(websocket: WebSocket, token: str = "", symbols: str = ""):
    """WebSocket market data stream — user-configurable symbol list.

    Usage:
      /ws/market?token=<jwt>&symbols=000001.SZ,600519.SH,300750.SZ
      /ws/market?symbols=000001.SZ          (no auth, single symbol)
      /ws/market                            (default: top 5 major indices)

    With token: subscribes to user's active strategy symbols automatically.
    Without token: uses explicit symbols param or defaults.
    """
=======
async def websocket_market(websocket: WebSocket):
    # Require token outside DEBUG to avoid anonymous quote scraping
    if not settings.DEBUG:
        token = websocket.query_params.get("token") or ""
        payload = decode_access_token(token) if token else None
        if not payload:
            await websocket.close(code=4001, reason="Unauthorized")
            return
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    await manager.connect(websocket)

    # Determine subscription list
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    elif token:
        payload = decode_access_token(token)
        if payload:
            username = payload.get("sub")
            if username:
                # Auto-subscribe to user's active strategy symbols
                from app.models.user import User as UserModel
                db = SessionLocal()
                try:
                    user = db.query(UserModel).filter(UserModel.username == username).first()
                    if user:
                        from app.models.strategy import Strategy as StrategyModel
                        strats = db.query(StrategyModel).filter(
                            StrategyModel.user_id == user.id,
                            StrategyModel.is_active == True,
                        ).all()
                        sym_set = set()
                        for s in strats:
                            for sym in (s.symbols or []):
                                sym_set.add(sym)
                        symbol_list = list(sym_set) if sym_set else ["000001.SZ", "600519.SH"]
                    else:
                        symbol_list = ["000001.SZ", "600519.SH"]
                except Exception:
                    symbol_list = ["000001.SZ", "600519.SH"]
                finally:
                    db.close()
            else:
                symbol_list = ["000001.SZ", "600519.SH"]
        else:
            symbol_list = ["000001.SZ", "600519.SH"]
    else:
        # Default: major indices + liquid large-caps
        symbol_list = ["000001.SZ", "600519.SH", "000333.SZ", "300750.SZ", "601318.SH"]

    print(f"[WebSocket] Market stream started: {len(symbol_list)} symbols")
    try:
        while True:
<<<<<<< HEAD
            loop = asyncio.get_running_loop()
            quotes_map = await loop.run_in_executor(None, data_engine.batch_get_quotes, symbol_list)
            for symbol in symbol_list:
                quote = quotes_map.get(symbol)
                if quote:
                    await websocket.send_json({
                        "type": "quote", "data": quote, "timestamp": datetime.now().isoformat()
                    })
                else:
=======
            symbols = ["000001.SZ", "600519.SH", "000333.SZ", "300750.SZ", "601318.SH"]
            try:
                quote_map = await asyncio.to_thread(
                    data_engine.get_realtime_quotes_batch, symbols
                ) or {}
            except Exception:
                quote_map = {}
            for symbol in symbols:
                quote = quote_map.get(symbol)
                if not quote:
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
                    await websocket.send_json({
                        "type": "quote",
                        "data": {
                            "symbol": symbol,
                            "current_price": 0,
                            "error": "fetch_failed",
                            "data_source": "error",
                        },
                        "timestamp": datetime.now().isoformat(),
                    })
<<<<<<< HEAD
            await asyncio.sleep(2)
=======
                else:
                    await websocket.send_json({
                        "type": "quote",
                        "data": quote,
                        "timestamp": datetime.now().isoformat(),
                    })
            await asyncio.sleep(5)
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Market stream error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str = ""):
    """WebSocket endpoint for real-time notification push.
    Authenticate via query parameter: /ws/notifications?token=<jwt_token>
    """
    await websocket.accept()

    if not token:
        await websocket.send_json({"type": "error", "data": {"message": "Missing token"}})
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.send_json({"type": "error", "data": {"message": "Invalid or expired token"}})
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    username = payload.get("sub")
    if not username:
<<<<<<< HEAD
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # JWT sub is username; notification_engine keys connections by integer user_id
=======
        await websocket.send_json({"type": "error", "data": {"message": "Invalid token payload"}})
        await websocket.close(code=4001, reason="Invalid token payload")
        return

>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
    finally:
        db.close()

<<<<<<< HEAD
    if not user:
=======
    if not user or not user.is_active:
        await websocket.send_json({"type": "error", "data": {"message": "User not found or inactive"}})
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
        await websocket.close(code=4001, reason="User not found")
        return

    user_id = user.id
<<<<<<< HEAD

    await websocket.accept()
=======
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    await notification_engine.connect(user_id, websocket)
    try:
        # Send a welcome message
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "通知通道已连接", "user_id": user_id},
        })
        # Keep connection alive, waiting for client messages or disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_engine.disconnect(user_id, websocket)
    except Exception as e:
        print(f"[WebSocket] Notification error for user {user_id}: {e}")
        notification_engine.disconnect(user_id, websocket)


@app.get("/api/health")
def health_check():
    db_ok = False
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "database": "connected" if db_ok else "unavailable",
        "allow_register": settings.ALLOW_REGISTER,  # login UI needs this
        "timestamp": datetime.now().isoformat(),
        **(
            {
                "allow_live": settings.ALLOW_LIVE_TRADING,
                "debug": settings.DEBUG,
            }
            if settings.DEBUG
            else {}
        ),
    }


def _init_database():
    """Initialize database; bootstrap first admin if empty; optionally seed demo."""
    try:
        init_db()
        print("[Startup] Database tables created")
    except Exception as e:
        print(f"[Startup] Database init failed: {e}")
        return

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            # Production often has SEED_DEMO_USERS=false + ALLOW_REGISTER=false —
            # without this, login is impossible on a fresh DB.
            username = (settings.BOOTSTRAP_ADMIN_USERNAME or "admin").strip() or "admin"
            password = settings.BOOTSTRAP_ADMIN_PASSWORD or "admin123"
            weak_passwords = {"admin123", "demo123", "password", "123456", "changeme"}
            if settings.REQUIRE_STRONG_SECRET and (
                password in weak_passwords or len(password) < 10
            ):
                raise RuntimeError(
                    "空库需要创建首个管理员，但 BOOTSTRAP_ADMIN_PASSWORD 过弱。"
                    "请在 .env 设置至少 10 位的强密码后再启动。"
                )
            admin = User(
                username=username,
                hashed_password=get_password_hash(password),
                display_name="管理员",
                role="admin",
                is_active=True,
                initial_cash=settings.DEFAULT_CASH,
            )
            db.add(admin)
            db.commit()
            print(
                f"[Startup] Bootstrapped first admin: {username} "
                f"(password from BOOTSTRAP_ADMIN_PASSWORD — change after login)"
            )
        elif settings.SEED_DEMO_USERS:
            admin_user = db.query(User).filter(User.username == "admin").first()
            if not admin_user:
                admin = User(
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    display_name="管理员",
                    role="admin",
                    is_active=True,
                    initial_cash=settings.DEFAULT_CASH,
                )
                db.add(admin)
                db.commit()
                print("[Startup] Admin user created: admin / admin123 — change immediately")

        if settings.SEED_DEMO_USERS:
            demo_user = db.query(User).filter(User.username == "demo").first()
            if not demo_user:
                demo = User(
                    username="demo",
                    hashed_password=get_password_hash("demo123"),
                    display_name="演示用户",
                    role="user",
                    is_active=True,
                    initial_cash=settings.DEFAULT_CASH,
                )
                db.add(demo)
                db.commit()
                print("[Startup] Demo user created: demo / demo123")
        else:
            print("[Startup] SEED_DEMO_USERS=false — skip demo account")
    except Exception as e:
        db.rollback()
        print(f"[Startup] User creation failed: {e}")
    finally:
        db.close()


def _order_maintenance_once() -> None:
    """Sync live fills + match paper limits (sync; run off the event loop)."""
    from app.engine.trading_engine import trading_engine
    db = SessionLocal()
    try:
        trading_engine.sync_live_orders(db)
        trading_engine.match_pending_limits(db)
    finally:
        db.close()


async def _order_maintenance_loop():
    """Background: sync live fills + match paper limits even without running strategies."""
    while True:
        try:
            await asyncio.to_thread(_order_maintenance_once)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Maintenance] Order sync error: {e}")
        await asyncio.sleep(15)


# ── Production static file serving ──────────────────────────────
# Set STATIC_DIR env var to the frontend dist/ folder to serve the SPA.
_static_dir = os.environ.get("STATIC_DIR", "")
if _static_dir:
    from fastapi.staticfiles import StaticFiles
    _static_path = os.path.abspath(_static_dir)
    if os.path.isdir(_static_path):
        # Mount /assets/ for JS/CSS (avoids shadowing WebSocket /ws/)
        assets_dir = os.path.join(_static_path, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Catch-all: serve index.html for all unmatched GET requests (SPA routing)
        from fastapi.responses import FileResponse, JSONResponse

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Don't intercept API/WebSocket paths
            if path.startswith("api/") or path.startswith("ws/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)

            # Prevent path traversal (e.g. ../backend/.env) when STATIC_DIR is set
            static_root = os.path.realpath(_static_path)
            candidate = os.path.realpath(os.path.join(static_root, path))
            if not (candidate == static_root or candidate.startswith(static_root + os.sep)):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            if os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(static_root, "index.html"))

        print(f"[Startup] Serving static files from {_static_path}")



async def _market_warmup_loop():
    """Background: prewarm avg-price env + sector ranking to avoid cold-start stalls."""
    from app.engine.market_env_engine import market_env_engine
    from app.engine.sector_engine import sector_engine

    # First pass shortly after boot (don't block startup)
    await asyncio.sleep(2)
    while True:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, market_env_engine.check_environment)
            await loop.run_in_executor(None, sector_engine.warm_cache)
            print("[Warmup] market env + sector ranking ready")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Warmup] failed: {e}")
        # Refresh within sector fresh TTL window
        await asyncio.sleep(max(120, int(getattr(settings, "SECTOR_CACHE_TTL", 300) * 0.8)))


@app.on_event("startup")
async def startup():
    default_secret = "quant-trading-secret-key-change-in-production"
    if settings.REQUIRE_STRONG_SECRET and settings.SECRET_KEY == default_secret:
        raise RuntimeError(
            "REQUIRE_STRONG_SECRET=true 但 SECRET_KEY 仍为默认值，拒绝启动。"
            "请在 .env 设置强随机 SECRET_KEY。"
        )
    if settings.SECRET_KEY == default_secret:
        print("[Startup] WARNING: SECRET_KEY 仍为默认值，生产环境请立即修改")
    if settings.ALLOW_LIVE_TRADING:
        print("[Startup] WARNING: ALLOW_LIVE_TRADING=true — 实盘通道已开启")
    if settings.ALLOW_REGISTER:
        print("[Startup] NOTICE: ALLOW_REGISTER=true — 开放自助注册")
    if settings.DEBUG:
        print("[Startup] NOTICE: DEBUG=true — 生产请设 DEBUG=false")

    _init_database()

    # Initialize broker connection
    try:
        from app.brokers import init_broker
        from app.core.config import settings
        broker_type = getattr(settings, "BROKER_TYPE", "paper")
        await init_broker(broker_type)
    except Exception as e:
        print(f"[Startup] Broker init skipped (paper mode fallback): {e}")

    asyncio.create_task(strategy_executor.startup())
    asyncio.create_task(_order_maintenance_loop())
    asyncio.create_task(_market_warmup_loop())
    print("[Startup] Server ready")


@app.on_event("shutdown")
async def shutdown():
    await strategy_executor.shutdown()

    # Disconnect broker
    try:
        from app.brokers import get_broker
        await get_broker().disconnect()
    except Exception:
        pass

    print("[Shutdown] Server stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
