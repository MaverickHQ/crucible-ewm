from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from services.core.broker.types import ExecutionEvent, OrderRequest
from services.core.state import State


class Broker(ABC):
    @abstractmethod
    def execute(
        self,
        orders: List[OrderRequest],
        price_context: Dict[str, float],
        starting_state: State | None = None,
    ) -> List[ExecutionEvent]:
        raise NotImplementedError
