from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from services.core.planner.types import Plan, PlanStep


class LocalPlanner:
    """
    LocalPlanner is a deterministic, non-LLM planner.

    Pack 19 Block 1 scope:
    - Provide a stable "planning surface" that we can later swap with Bedrock planner.
    - When enabled, create a simple plan that mirrors the loop inputs:
        - validate inputs
        - generate market path
        - load strategy
        - run loop
        - return summary
    """

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def make_plan(
        self,
        *,
        symbols: List[str],
        steps: int,
        seed: int,
        write_artifacts: bool,
        budgets: Dict[str, int],
    ) -> Optional[Plan]:
        if not self.enabled:
            return None

        plan_steps = [
            PlanStep(
                tool="validate_request",
                args={
                    "symbols": symbols,
                    "steps": steps,
                    "seed": seed,
                    "write_artifacts": write_artifacts,
                    "budgets": budgets,
                },
                rationale="Validate request schema + budgets before simulation.",
            ),
            PlanStep(
                tool="generate_market_path",
                args={"tickers": symbols, "n_steps": steps, "seed": seed},
                rationale="Create deterministic market path fixture from seed.",
            ),
            PlanStep(
                tool="load_strategy",
                args={"strategy": "examples/strategies/threshold_demo.json"},
                rationale="Load local strategy spec used by loop-no-llm demo.",
            ),
            PlanStep(
                tool="run_loop",
                args={"steps": steps, "write_artifacts": write_artifacts},
                rationale="Execute the loop using MarketPath + Strategy.",
            ),
            PlanStep(
                tool="summarize",
                args={},
                rationale="Summarize final state and artifact outputs.",
            ),
        ]
        return Plan(steps=plan_steps, meta={"planner": "local", "version": "pack19-block1"})

    @staticmethod
    def to_dict(plan: Plan) -> Dict[str, Any]:
        return {
            "steps": [asdict(s) for s in plan.steps],
            "meta": dict(plan.meta),
        }
