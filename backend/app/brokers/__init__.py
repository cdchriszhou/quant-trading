"""Broker Abstraction Layer — pluggable trading backends.

Usage:
    from app.brokers import get_broker, create_broker

    # On startup:
    broker = create_broker("qmt")  # or "paper"
    await broker.connect()

    # In TradingEngine:
    result = await broker.submit_order(OrderRequest(...))
"""

import logging
from typing import Optional

from app.brokers.base import (
    BaseBroker, BrokerError, BrokerState, BrokerConnectionState,
    OrderSide, OrderType, OrderStatus,
    OrderRequest, OrderResult, PositionInfo, AccountInfo,
)
from app.brokers.paper import PaperBroker

logger = logging.getLogger("broker")


# ── Global broker instance ─────────────────────────────────────────

_broker: Optional[BaseBroker] = None


def get_broker() -> BaseBroker:
    """Get the current global broker instance.

    If no broker has been explicitly created, returns a PaperBroker
    (safe default for development / testing).
    """
    global _broker
    if _broker is None:
        _broker = PaperBroker()
        logger.info("[Broker] Defaulting to PaperBroker (no broker configured)")
    return _broker


async def init_broker(broker_type: str = "", **kwargs) -> BaseBroker:
    """Initialize and connect the global broker instance.

    Called once on application startup. If broker_type is empty,
    reads BROKER_TYPE from settings / env.

    Args:
        broker_type: "paper", "qmt", "xtp", "ptrade", "ctp", or "custom"
        **kwargs: passed to the broker constructor

    Returns:
        Connected broker instance.

    Raises:
        BrokerError: on connection failure.
    """
    global _broker

    broker = create_broker(broker_type, **kwargs)
    await broker.connect()

    _broker = broker
    logger.info(f"[Broker] Activated: {broker.broker_type}")
    return broker


def create_broker(broker_type: str = "", **kwargs) -> BaseBroker:
    """Create a broker instance without connecting.

    Args:
        broker_type: "paper", "qmt", etc. Empty = read from settings.
        **kwargs: broker-specific config.
    """
    if not broker_type:
        from app.core.config import settings
        broker_type = getattr(settings, "BROKER_TYPE", "paper")

    broker_type = broker_type.lower().strip()

    if broker_type == "paper":
        return PaperBroker(**kwargs)

    elif broker_type == "qmt":
        from app.brokers.qmt import QMTBroker
        return QMTBroker(**kwargs)

    elif broker_type == "xtp":
        raise BrokerError(
            "XTP broker not yet implemented. "
            "See brokers/qmt.py as a reference to implement your own.",
            code="BROKER_NOT_IMPLEMENTED",
        )

    elif broker_type == "ptrade":
        raise BrokerError(
            "PTrade broker not yet implemented.",
            code="BROKER_NOT_IMPLEMENTED",
        )

    elif broker_type == "ctp":
        raise BrokerError(
            "CTP broker not yet implemented.",
            code="BROKER_NOT_IMPLEMENTED",
        )

    elif broker_type == "custom":
        # Load user-provided broker class
        custom_path = kwargs.get("custom_path", "")
        if not custom_path:
            raise BrokerError(
                "Custom broker requires 'custom_path' kwarg pointing to the adapter module.",
                code="BROKER_NO_CUSTOM_PATH",
            )
        import importlib
        spec = importlib.util.spec_from_file_location("custom_broker", custom_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        broker_cls = getattr(mod, "CustomBroker", None)
        if broker_cls is None:
            raise BrokerError(
                f"Custom broker module at {custom_path} must export a 'CustomBroker' class.",
                code="BROKER_NO_CUSTOM_CLASS",
            )
        return broker_cls(**kwargs)

    else:
        raise BrokerError(
            f"Unknown broker type: {broker_type}. "
            f"Supported: paper, qmt, xtp, ptrade, ctp, custom",
            code="BROKER_UNKNOWN",
        )


# ── Re-export commonly used types ──────────────────────────────────

__all__ = [
    "BaseBroker", "BrokerError", "BrokerState", "BrokerConnectionState",
    "OrderSide", "OrderType", "OrderStatus",
    "OrderRequest", "OrderResult", "PositionInfo", "AccountInfo",
    "PaperBroker",
    "get_broker", "init_broker", "create_broker",
]
