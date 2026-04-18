from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class OrderRequest:
    run_id: str
    step_index: int
    action_index: int
    symbol: str
    side: str
    quantity: float
    limit_price: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "step_index": self.step_index,
            "action_index": self.action_index,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
        }


@dataclass(frozen=True)
class OrderFill:
    fill_price: float
    filled_qty: float
    status: str = "FILLED"

    def to_dict(self) -> Dict[str, object]:
        return {
            "fill_price": self.fill_price,
            "filled_qty": self.filled_qty,
            "status": self.status,
        }


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    run_id: str
    step_index: int
    action_index: int
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    cash_before: float
    cash_after: float
    positions_before: Dict[str, float]
    positions_after: Dict[str, float]
    exposure_before: float
    exposure_after: float
    why: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "step_index": self.step_index,
            "action_index": self.action_index,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status,
            "cash_before": self.cash_before,
            "cash_after": self.cash_after,
            "positions_before": dict(self.positions_before),
            "positions_after": dict(self.positions_after),
            "exposure_before": self.exposure_before,
            "exposure_after": self.exposure_after,
            "why": self.why,
        }
