"""Notification Engine: Create, persist, and broadcast notifications."""

import json
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.notification import Notification
from app.engine.data_engine import data_engine

logger = logging.getLogger("notification_engine")


class NotificationEngine:
    """Manages notification lifecycle: creation, persistence, and WebSocket broadcast.

    Usage:
        notifier = NotificationEngine()
        notifier.broadcast = my_websocket_broadcast_func
        notifier.create(user_id=1, type="signal_buy", title="...", ...)
    """

    def __init__(self):
        self._connections: dict[int, list] = {}  # user_id -> [websocket, ...]
        self.broadcast = self._default_broadcast

    # ── WebSocket connection management ───────────────────────────

    async def connect(self, user_id: int, websocket):
        """Register a WebSocket connection for a user."""
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info(f"[Notify] User {user_id} connected (total: {len(self._connections[user_id])})")

    def disconnect(self, user_id: int, websocket):
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [ws for ws in self._connections[user_id] if ws is not websocket]
            if not self._connections[user_id]:
                del self._connections[user_id]
            logger.info(f"[Notify] User {user_id} disconnected")

    # ── Notification creation ─────────────────────────────────────

    def create(
        self,
        user_id: int,
        type: str,
        title: str,
        message: Optional[str] = None,
        strategy_id: Optional[int] = None,
        strategy_name: Optional[str] = None,
        order_id: Optional[int] = None,
        symbol: Optional[str] = None,
        price: Optional[str] = None,
    ) -> Optional[dict]:
        """Create and persist a notification, then broadcast via WebSocket."""
        db = SessionLocal()
        try:
            notif = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                order_id=order_id,
                symbol=symbol,
                price=price,
                is_read=False,
                created_at=datetime.now(),
            )
            db.add(notif)
            db.commit()
            db.refresh(notif)
            data = notif.to_dict()

            # Broadcast to connected user(s)
            asyncio.ensure_future(self.broadcast(user_id, data))

            return data
        except Exception as e:
            logger.error(f"[Notify] Failed to create notification: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    async def _default_broadcast(self, user_id: int, data: dict):
        """Default: push to all WebSocket connections for this user."""
        ws_list = self._connections.get(user_id, [])
        dead = []
        for ws in ws_list:
            try:
                await ws.send_json({"type": "notification", "data": data})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    # ── Convenience helpers ────────────────────────────────────────

    def signal_buy(
        self, user_id: int, symbol: str, price: float,
        strategy_id: int, strategy_name: str, message: str = "",
    ):
        """Notify: buy signal triggered."""
        return self.create(
            user_id=user_id,
            type="signal_buy",
            title=f"📈 买入信号 — {symbol}",
            message=message or f"策略「{strategy_name}」对 {symbol} 发出买入信号，参考价 ¥{price:.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            price=f"¥{price:.2f}",
        )

    def signal_sell(
        self, user_id: int, symbol: str, price: float,
        strategy_id: int, strategy_name: str, reason: str = "",
    ):
        """Notify: sell signal triggered."""
        return self.create(
            user_id=user_id,
            type="signal_sell",
            title=f"📉 卖出信号 — {symbol}",
            message=reason or f"策略「{strategy_name}」对 {symbol} 发出卖出信号，参考价 ¥{price:.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            price=f"¥{price:.2f}",
        )

    def order_placed(
        self, user_id: int, symbol: str, side: str, price: float,
        quantity: float, strategy_id: int, strategy_name: str, order_id: int,
    ):
        """Notify: order submitted."""
        side_cn = "买入" if side == "buy" else "卖出"
        return self.create(
            user_id=user_id,
            type="order_placed",
            title=f"✅ 订单已提交 — {side_cn} {symbol}",
            message=f"策略「{strategy_name}」自动{side_cn} {symbol} x{quantity:.0f}股 @ ¥{price:.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            order_id=order_id,
            symbol=symbol,
            price=f"¥{price:.2f}",
        )

    def risk_blocked(
        self, user_id: int, symbol: str, side: str, price: float,
        strategy_id: int, strategy_name: str, violations: list,
    ):
        """Notify: order blocked by risk control."""
        side_cn = "买入" if side == "buy" else "卖出"
        details = "; ".join(
            f"{v.get('rule_name', v)}" for v in (violations or [])
        )
        return self.create(
            user_id=user_id,
            type="risk_blocked",
            title=f"🛡️ 风控拦截 — {symbol}",
            message=f"策略「{strategy_name}」{side_cn} {symbol} 被风控拦截。原因: {details}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            price=f"¥{price:.2f}",
        )

    def stop_loss(self, user_id: int, symbol: str, price: float,
                   strategy_id: int, strategy_name: str):
        """Notify: stop loss triggered."""
        return self.create(
            user_id=user_id,
            type="stop_loss",
            title=f"⛔ 止损触发 — {symbol}",
            message=f"策略「{strategy_name}」中 {symbol} 触发止损 @ ¥{price:.2f}",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            price=f"¥{price:.2f}",
        )

    def system(self, user_id: int, title: str, message: str):
        """Notify: system message."""
        return self.create(
            user_id=user_id,
            type="system",
            title=title,
            message=message,
        )


notification_engine = NotificationEngine()
