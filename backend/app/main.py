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
from app.api.v1 import auth, market, strategy_api, trading, backtest, risk, reports, admin, notifications, env, sector
from app.engine.data_engine import data_engine
from app.engine.strategy_executor import strategy_executor
from app.engine.notification_engine import notification_engine
from app.core.security import decode_access_token

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
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
async def websocket_market(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            symbols = ["000001.SZ", "600519.SH", "000333.SZ", "300750.SZ", "601318.SH"]
            for symbol in symbols:
                try:
                    loop = asyncio.get_running_loop()
                    quote = await loop.run_in_executor(None, data_engine.get_realtime_quote, symbol)
                    await websocket.send_json({"type": "quote", "data": quote, "timestamp": datetime.now().isoformat()})
                except RuntimeError:
                    # Single quote failure — send error for this symbol, keep going
                    await websocket.send_json({
                        "type": "quote",
                        "data": {"symbol": symbol, "current_price": 0, "error": "fetch_failed", "data_source": "error"},
                        "timestamp": datetime.now().isoformat(),
                    })
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)
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
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    await websocket.accept()
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
    return {"status": "ok", "database": "connected" if db_ok else "unavailable", "timestamp": datetime.now().isoformat()}


def _init_database():
    """Initialize database and create default users. Runs synchronously on startup."""
    try:
        init_db()
        print("[Startup] Database tables created")
    except Exception as e:
        print(f"[Startup] Database init failed: {e}")
        return

    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin = User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                display_name="管理员",
                role="admin",
                is_active=True,
                initial_cash=1000000,
            )
            db.add(admin)
            db.commit()
            print("[Startup] Admin user created: admin / admin123")

        demo_user = db.query(User).filter(User.username == "demo").first()
        if not demo_user:
            demo = User(
                username="demo",
                hashed_password=get_password_hash("demo123"),
                display_name="演示用户",
                role="user",
                is_active=True,
                initial_cash=1000000,
            )
            db.add(demo)
            db.commit()
            print("[Startup] Demo user created: demo / demo123")
    except Exception as e:
        db.rollback()
        print(f"[Startup] User creation failed: {e}")
    finally:
        db.close()


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
        from fastapi.responses import FileResponse
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Don't intercept API/WebSocket paths
            if path.startswith("api/") or path.startswith("ws/"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            file_path = os.path.join(_static_path, path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(_static_path, "index.html"))

        print(f"[Startup] Serving static files from {_static_path}")



@app.on_event("startup")
async def startup():
    _init_database()
    asyncio.create_task(strategy_executor.startup())
    print("[Startup] Server ready")


@app.on_event("shutdown")
async def shutdown():
    await strategy_executor.shutdown()
    print("[Shutdown] Server stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
