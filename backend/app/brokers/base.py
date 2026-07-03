"""Broker Abstraction Layer — unified interface for paper & live trading.

All broker implementations MUST inherit from BaseBroker and implement every
abstract method. The TradingEngine delegates all order/position operations
to the currently active broker instance.

Supported broker types:
  - paper      — simulated trading (built-in, no external dependency)
  - qmt        — 迅投QMT / MiniQMT (popular Chinese retail quant platform)
  - xtp        — 中泰XTP (low-latency C++ API with Python bindings)
  - ptrade     — 恒生PTrade
  - ctp        — 综合交易平台 (futures)
  - custom     — user-provided adapter
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ── Shared data types ──────────────────────────────────────────────


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class BrokerConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class OrderRequest:
    """Standardised order request sent to the broker."""
    symbol: str                # e.g. "000001.SZ" or "600519.SH"
    side: OrderSide
    order_type: OrderType
    quantity: float            # shares (stock) or contracts (futures)
    price: float = 0.0         # 0 = market order
    strategy_id: int | None = None
    remark: str = ""


@dataclass
class OrderResult:
    """Standardised order result returned by the broker."""
    broker_order_id: str       # broker-assigned order ID (e.g. "20250703_000001")
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: float
    filled_quantity: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    commission: float = 0.0
    error_message: str = ""
    raw_response: dict | None = None  # original broker response for debugging


@dataclass
class PositionInfo:
    """Standardised position snapshot from the broker."""
    symbol: str
    name: str = ""
    quantity: float = 0.0           # total holding
    available_quantity: float = 0.0  # sellable today
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


@dataclass
class AccountInfo:
    """Standardised account snapshot from the broker."""
    account_id: str = ""
    total_assets: float = 0.0       # 总资产
    available_cash: float = 0.0      # 可用资金
    frozen_cash: float = 0.0         # 冻结资金
    market_value: float = 0.0        # 持仓市值
    total_pnl: float = 0.0           # 累计盈亏
    total_return_pct: float = 0.0    # 总收益率


@dataclass
class BrokerState:
    """Current state of the broker connection."""
    connection: BrokerConnectionState = BrokerConnectionState.DISCONNECTED
    broker_type: str = ""
    account_info: AccountInfo | None = None
    last_heartbeat: datetime | None = None
    error_message: str = ""


# ── Abstract Broker Interface ──────────────────────────────────────


class BaseBroker(ABC):
    """Abstract interface that every broker adapter must implement.

    Lifecycle:
      1. __init__()          — load config, no network I/O
      2. connect()           — authenticate, establish session
      3. [ trading operations ]
      4. disconnect()        — clean up session

    Thread-safety:
      Implementations must be safe to call from multiple threads (the
      strategy executor runs order operations on asyncio thread pools).
    """

    broker_type: str = "base"

    # ── Lifecycle ──────────────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> BrokerState:
        """Authenticate and establish connection to the broker.

        Called once on startup. Raises BrokerError on failure.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the broker connection. Idempotent."""
        ...

    @abstractmethod
    def get_state(self) -> BrokerState:
        """Return current connection state (non-blocking)."""
        ...

    # ── Order operations ───────────────────────────────────────────

    @abstractmethod
    async def submit_order(self, req: OrderRequest) -> OrderResult:
        """Submit an order to the broker for execution.

        Args:
            req: Standardised order request.

        Returns:
            OrderResult with broker-assigned order ID and status.

        Raises:
            BrokerError: on connection failure, rejection, or timeout.
        """
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str, symbol: str) -> OrderResult:
        """Cancel a pending order by its broker-assigned ID."""
        ...

    @abstractmethod
    async def query_order(self, broker_order_id: str) -> OrderResult:
        """Query the current status of a previously submitted order."""
        ...

    # ── Position & Account ─────────────────────────────────────────

    @abstractmethod
    async def get_positions(self) -> list[PositionInfo]:
        """Fetch all current positions from the broker.

        Called every time the frontend requests position data.
        Must return real-time market values.
        """
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Fetch account summary: assets, cash, PnL.

        Called by the frontend and by strategy executor for risk checks.
        """
        ...

    # ── Market Data (optional override) ────────────────────────────

    async def get_realtime_quote(self, symbol: str) -> dict:
        """Get real-time quote from the broker's market data feed.

        Default: delegates to the system DataEngine (Tencent API).
        Override to use the broker's own Level-2 data for lower latency.
        """
        from app.engine.data_engine import data_engine
        loop = __import__('asyncio').get_running_loop()
        return await loop.run_in_executor(None, data_engine.get_realtime_quote, symbol)

    async def batch_get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Batch-get real-time quotes. Override for broker-native batch API."""
        from app.engine.data_engine import data_engine
        loop = __import__('asyncio').get_running_loop()
        return await loop.run_in_executor(None, data_engine.batch_get_quotes, symbols)


# ── Broker Error ───────────────────────────────────────────────────


class BrokerError(Exception):
    """Unified exception for all broker-related errors."""
    def __init__(self, message: str, code: str = "", recoverable: bool = False):
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable
