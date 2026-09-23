"""Paper broker — real market prices + simulated cash ledger."""

from typing import Optional

from app.engine.broker.base import BrokerGateway, BrokerOrderResult, BrokerStatus


class PaperBroker(BrokerGateway):
    name = "paper"

    def status(self) -> BrokerStatus:
        return BrokerStatus(
            broker="paper",
            connected=True,
            account_id="SIMULATED",
            message="模拟资金账户：行情/费率真实，资金为本地模拟账本",
        )

    def get_cash(self) -> float:
        # Cash is owned by TradingEngine ledger for the user
        return 0.0

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> BrokerOrderResult:
        # Paper fills are handled inside TradingEngine._execute_order
        return BrokerOrderResult(
            success=True,
            broker_order_id="paper-local",
            status="filled",
            filled_price=price,
            filled_quantity=quantity,
            message="paper local fill",
        )
