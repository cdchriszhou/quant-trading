"""A-share fee calculator — mirrors current China equity fee schedule.

Rates (as of 2023-08 stamp duty cut; transfer fee unified):
  - Commission: broker-negotiated, default 万2.5, floor ¥5 (both sides)
  - Stamp duty: 0.05% sell only (印花税)
  - Transfer fee: 0.001% both sides (过户费, 沪深)
"""

from dataclasses import dataclass
from app.core.config import settings


@dataclass
class FeeBreakdown:
    amount: float
    commission: float
    stamp_duty: float
    transfer_fee: float
    total: float
    side: str

    def to_dict(self) -> dict:
        return {
            "amount": round(self.amount, 2),
            "commission": round(self.commission, 2),
            "stamp_duty": round(self.stamp_duty, 2),
            "transfer_fee": round(self.transfer_fee, 2),
            "total": round(self.total, 2),
            "side": self.side,
            "rates": {
                "commission_rate": settings.COMMISSION_RATE,
                "min_commission": settings.MIN_COMMISSION,
                "stamp_duty_rate": settings.STAMP_DUTY_RATE,
                "transfer_fee_rate": settings.TRANSFER_FEE_RATE,
            },
        }


class FeeEngine:
    """Compute realistic A-share trading costs."""

    def calculate(self, side: str, price: float, quantity: float) -> FeeBreakdown:
        amount = abs(float(price) * float(quantity))
        commission = max(amount * settings.COMMISSION_RATE, settings.MIN_COMMISSION)
        stamp = amount * settings.STAMP_DUTY_RATE if side == "sell" else 0.0
        transfer = amount * settings.TRANSFER_FEE_RATE
        total = commission + stamp + transfer
        return FeeBreakdown(
            amount=amount,
            commission=commission,
            stamp_duty=stamp,
            transfer_fee=transfer,
            total=total,
            side=side,
        )

    def buy_cost(self, price: float, quantity: float) -> float:
        """Cash required to buy (amount + fees)."""
        fee = self.calculate("buy", price, quantity)
        return fee.amount + fee.total

    def sell_proceeds(self, price: float, quantity: float) -> float:
        """Cash received after sell fees."""
        fee = self.calculate("sell", price, quantity)
        return fee.amount - fee.total


fee_engine = FeeEngine()
