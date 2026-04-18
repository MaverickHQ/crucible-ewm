from __future__ import annotations

from typing import Dict

from ewm_core.actions import PlaceBuy
from ewm_core.planner.base import Planner
from ewm_core.planner.types import PlannerResult


class MockPlanner(Planner):
    name = "mock"

    def propose(
        self,
        state_summary: Dict[str, object],
        policy: Dict[str, object],
        goal: str,
    ) -> PlannerResult:
        if goal == "approve":
            plan = [
                PlaceBuy(symbol="AAPL", quantity=1, price=0.0),
                PlaceBuy(symbol="MSFT", quantity=1, price=0.0),
            ]
            return PlannerResult(plan=plan, planner_name=self.name, metadata={"goal": goal})

        plan = [
            PlaceBuy(symbol="AAPL", quantity=1, price=0.0),
            PlaceBuy(symbol="AAPL", quantity=20, price=0.0),
        ]
        return PlannerResult(plan=plan, planner_name=self.name, metadata={"goal": goal})
