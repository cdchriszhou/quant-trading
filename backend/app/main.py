"""Quant Trading System — FastAPI Application Entry Point."""

import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.api.v1 import auth, market, strategy_api, trading, backtest, risk, reports, admin
from app.engine.data_engine import data_engine

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
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(strategy_api.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


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
                quote = data_engine.get_realtime_quote(symbol)
                await websocket.send_json({"type": "quote", "data": quote, "timestamp": datetime.now().isoformat()})
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)


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


@app.on_event("startup")
async def startup():
    _init_database()
    print("[Startup] Server ready")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
