"""Broker registry."""

from app.core.config import settings
from app.engine.broker.base import BrokerGateway
from app.engine.broker.paper import PaperBroker
from app.engine.broker.qmt import QmtBroker

_paper = PaperBroker()
_qmt = QmtBroker()


def get_broker(mode: str = "paper") -> BrokerGateway:
    """Return broker for account mode. live → configured live broker."""
    if mode == "live":
        if settings.BROKER_TYPE == "qmt":
            return _qmt
        # Unknown live broker — still return qmt adapter for status messaging
        return _qmt
    return _paper


def broker_status(mode: str = "paper", connect: bool = True) -> dict:
    broker = get_broker(mode)
    if mode == "live" and hasattr(broker, "status"):
        try:
            return broker.status(connect=connect).to_dict()  # type: ignore[call-arg]
        except TypeError:
            return broker.status().to_dict()
    return broker.status().to_dict()


def reset_live_broker() -> None:
    """Force MiniQMT session rebuild after config change."""
    if hasattr(_qmt, "reset"):
        _qmt.reset()
