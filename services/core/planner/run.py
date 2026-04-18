from __future__ import annotations

from typing import Dict

from services.core.market import MarketPath
from services.core.planner.base import Planner
from services.core.planner.types import PlannerRejection, PlannerResult
from services.core.simulator import SimulationResult, simulate_plan
from services.core.state import State


def run_planned_simulation(
    planner: Planner,
    initial_state: State,
    market_path: MarketPath,
    policy: Dict[str, object],
    goal: str,
    state_summary: Dict[str, object],
) -> tuple[PlannerResult, SimulationResult]:
    planner_result = planner.propose(state_summary, policy, goal)

    simulation = simulate_plan(
        initial_state,
        planner_result.plan,
        market_path,
        policy_id=policy.get("policy_id"),
        policy_version=policy.get("policy_version"),
        policy_hash=policy.get("policy_hash"),
        planner_name=planner_result.planner_name,
        planner_metadata=planner_result.metadata,
    )

    if not simulation.approved:
        violations = [
            {"code": error.code, "message": error.message}
            for error in simulation.steps[simulation.rejected_step_index].errors
        ]
        planner_result.rejection = PlannerRejection(
            rejected_step_index=simulation.rejected_step_index,
            violations=violations,
        )

    return planner_result, simulation
