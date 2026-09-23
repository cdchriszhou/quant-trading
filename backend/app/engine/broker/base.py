"""Broker gateway abstraction — paper (simulated cash) vs live (real account)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrokerStatus:
    broker: str
    connected: bool
    account_id: str = ""
    message: str = ""
    cash: Optional[float] = None
    market_value: Optional[float] = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "broker": self.broker,
            "connected": self.connected,
            "account_id": self.account_id,
            "message": self.message,
            "cash": self.cash,
            "market_value": self.market_value,
            "details": self.details,
        }


@dataclass
class BrokerOrderResult:
    success: bool
    broker_order_id: str = ""
    status: str = "rejected"
    filled_price: Optional[float] = None
    filled_quantity: Optional[float] = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "broker_order_id": self.broker_order_id,
            "status": self.status,
            "filled_price": self.filled_price,
            "filled_quantity": self.filled_quantity,
            "message": self.message,
        }


class BrokerGateway(ABC):
    name: str = "base"

    @abstractmethod
    def status(self) -> BrokerStatus:
        ...

    @abstractmethod
    def get_cash(self) -> float:
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> BrokerOrderResult:
        ...

    def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        """Optional — live brokers should override."""
        return BrokerOrderResult(
            success=False,
            message=f"{self.name} 不支持撤单接口",
        )

    def query_order(self, broker_order_id: str) -> BrokerOrderResult:
        """Optional — poll fill status for a broker order id."""
        return BrokerOrderResult(
            success=False,
            broker_order_id=broker_order_id,
            status="unknown",
            message=f"{self.name} 不支持订单查询",
        )
