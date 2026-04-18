from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class RiskLimits:
    max_leverage: float
    max_position_pct: float
    max_position_value: float


@dataclass(frozen=True)
class State:
    cash_balance: float
    positions: Dict[str, float] = field(default_factory=dict)
    exposure: float = 0.0
    risk_limits: RiskLimits = field(
        default_factory=lambda: RiskLimits(
            max_leverage=1.0,
            max_position_pct=0.5,
            max_position_value=100_000.0,
        )
    )

    def with_positions(self, positions: Dict[str, float], prices: Dict[str, float]) -> "State":
        exposure = sum(abs(qty * prices.get(symbol, 0.0)) for symbol, qty in positions.items())
        return State(
            cash_balance=self.cash_balance,
            positions=positions,
            exposure=exposure,
            risk_limits=self.risk_limits,
        )

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash_balance + sum(
            qty * prices.get(symbol, 0.0) for symbol, qty in self.positions.items()
        )

    def exposure_value(self, prices: Dict[str, float]) -> float:
        return sum(abs(qty * prices.get(symbol, 0.0)) for symbol, qty in self.positions.items())

    def to_dict(self) -> Dict[str, object]:
        return {
            "cash_balance": self.cash_balance,
            "positions": dict(self.positions),
            "exposure": self.exposure,
            "risk_limits": {
                "max_leverage": self.risk_limits.max_leverage,
                "max_position_pct": self.risk_limits.max_position_pct,
                "max_position_value": self.risk_limits.max_position_value,
            },
        }
