from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from ewm_core.broker.types import ExecutionEvent, OrderRequest
from ewm_core.state import State


class Broker(ABC):
    @abstractmethod
    def execute(
        self,
        orders: List[OrderRequest],
        price_context: Dict[str, float],
        starting_state: State | None = None,
    ) -> List[ExecutionEvent]:
        raise NotImplementedError
