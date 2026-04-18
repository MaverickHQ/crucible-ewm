from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from services.core.broker.types import ExecutionEvent
from services.core.observability import TapeRow
from services.core.state import State


@dataclass(frozen=True)
class ExecutionRow:
    step_index: int
    run_id: str
    decision: str
    symbol: str
    side: str
    quantity: float
    price: float
    cash_before: float
    cash_after: float
    exposure_before: float
    exposure_after: float
    positions_before: Dict[str, float]
    positions_after: Dict[str, float]
    reason: str
    verification: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "step_index": self.step_index,
            "run_id": self.run_id,
            "decision": self.decision,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "cash_before": self.cash_before,
            "cash_after": self.cash_after,
            "exposure_before": self.exposure_before,
            "exposure_after": self.exposure_after,
            "positions_before": dict(self.positions_before),
            "positions_after": dict(self.positions_after),
            "reason": self.reason,
            "verification": self.verification,
        }


@dataclass(frozen=True)
class ExecutionBundle:
    step_index: int
    run_id: str
    artifact_dir: str
    events: List[ExecutionEvent]
    ledger_rows: List[ExecutionRow]

    def to_dict(self) -> Dict[str, object]:
        return {
            "step_index": self.step_index,
            "run_id": self.run_id,
            "artifact_dir": self.artifact_dir,
            "events": [event.to_dict() for event in self.events],
            "ledger_rows": [row.to_dict() for row in self.ledger_rows],
        }


@dataclass(frozen=True)
class LoopResult:
    tape_rows: List[TapeRow]
    execution_rows: List[ExecutionRow]
    execution_bundles: List[ExecutionBundle]
    final_state: State
