from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from services.core.planner.types import PlannerResult


class Planner(ABC):
    name: str = "planner"

    @abstractmethod
    def propose(
        self,
        state_summary: Dict[str, object],
        policy: Dict[str, object],
        goal: str,
    ) -> PlannerResult:
        raise NotImplementedError
