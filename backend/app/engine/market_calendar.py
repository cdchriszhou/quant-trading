"""A-share market calendar helpers (Asia/Shanghai)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI)


def trading_day_start(now: datetime | None = None) -> datetime:
    """Start of the current Shanghai calendar day (naive UTC-comparable local midnight).

    Stored timestamps in DB are naive (historically utcnow). For T+1 / daily loss we
    compare against Shanghai midnight expressed as naive local wall time, which matches
    how China equity sessions are reasoned about in this app.
    """
    n = now or shanghai_now()
    if n.tzinfo is not None:
        n = n.astimezone(SHANGHAI).replace(tzinfo=None)
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


def is_weekday(now: datetime | None = None) -> bool:
    n = now or shanghai_now()
    if n.tzinfo is not None:
        n = n.astimezone(SHANGHAI)
    return n.weekday() < 5


def is_a_share_trading_session(now: datetime | None = None) -> bool:
    """True during continuous auction: 09:30–11:30 and 13:00–15:00 weekdays.

    Does not model holidays (would need exchange calendar data).
    """
    n = now or shanghai_now()
    if n.tzinfo is not None:
        n = n.astimezone(SHANGHAI)
    if n.weekday() >= 5:
        return False
    t = n.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    return morning or afternoon


def next_session_hint(now: datetime | None = None) -> str:
    n = now or shanghai_now()
    if n.tzinfo is not None:
        n = n.astimezone(SHANGHAI)
    if is_a_share_trading_session(n):
        return "交易时段中"
    if n.weekday() >= 5:
        return "非交易日"
    t = n.time()
    if t < time(9, 30):
        return "未开盘"
    if time(11, 30) < t < time(13, 0):
        return "午间休市"
    return "已收盘"
