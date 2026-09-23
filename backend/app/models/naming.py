"""Shared helpers for model serialization."""

from __future__ import annotations

_name_cache: dict[str, str] = {}


def resolve_symbol_name(symbol: str | None) -> str:
    """Resolve A-share Chinese name; cached in-process."""
    if not symbol:
        return ""
    if symbol in _name_cache:
        return _name_cache[symbol]
    try:
        from app.engine.data_engine import data_engine
        name = data_engine.lookup_stock_name(symbol) or ""
        # lookup may return the code itself on miss — treat as empty for UI
        bare = symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        if name in (symbol, bare, ""):
            name = ""
        _name_cache[symbol] = name
        return name
    except Exception:
        return ""
