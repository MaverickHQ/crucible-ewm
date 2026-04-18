from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional
from uuid import uuid4

from services.core.actions import PlaceBuy, PlaceSell
from services.core.market import MarketPath
from services.core.state import State
from services.core.transitions import Action, TransitionResult, apply_action
from services.core.verifier import VerificationError, VerificationResult, verify_transition


@dataclass(frozen=True)
class StepResult:
    step_index: int
    action: Action
    accepted: bool
    errors: List[VerificationError]
    price_context: dict
    explanation: str
    state_delta: Dict[str, object]


@dataclass(frozen=True)
class SimulationResult:
    run_id: str
    trajectory: List[State]
    steps: List[StepResult]
    approved: bool
    rejected_step_index: Optional[int]
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    policy_hash: Optional[str] = None
    planner_name: Optional[str] = None
    planner_metadata: Optional[Dict[str, object]] = None


def _apply_market_price(action: Action, price_context: dict) -> Action:
    price = price_context[action.symbol]
    if isinstance(action, PlaceBuy):
        return replace(action, price=price)
    if isinstance(action, PlaceSell):
        return replace(action, price=price)
    return action


def simulate_plan(
    initial_state: State,
    plan: List[Action],
    market_path: MarketPath,
    policy_id: Optional[str] = None,
    policy_version: Optional[str] = None,
    policy_hash: Optional[str] = None,
    planner_name: Optional[str] = None,
    planner_metadata: Optional[Dict[str, object]] = None,
    run_id: Optional[str] = None,
) -> SimulationResult:
    trajectory: List[State] = [initial_state]
    step_results: List[StepResult] = []
    rejected_index: Optional[int] = None

    for step_index, action in enumerate(plan):
        price_context = market_path.price_context(step_index)
        priced_action = _apply_market_price(action, price_context)
        verification: VerificationResult = verify_transition(trajectory[-1], priced_action)

        if verification.accepted:
            transition: TransitionResult = apply_action(trajectory[-1], priced_action)
            next_state = transition.next_state
        else:
            transition = TransitionResult(
                prior=trajectory[-1],
                action=priced_action,
                next_state=trajectory[-1],
                prices=price_context,
            )
            next_state = trajectory[-1]

        from services.core.deltas.compute import compute_state_delta
        from services.core.explain.explain import explain_transition

        state_delta = compute_state_delta(transition.prior, next_state, price_context)
        explanation = explain_transition(
            transition.prior,
            priced_action,
            next_state,
            verification,
            price_context,
        )

        step_results.append(
            StepResult(
                step_index=step_index,
                action=priced_action,
                accepted=verification.accepted,
                errors=verification.errors,
                price_context=price_context,
                explanation=explanation,
                state_delta=state_delta,
            )
        )

        if not verification.accepted:
            rejected_index = step_index
            break

        trajectory.append(next_state)

    approved = rejected_index is None

    # Use provided run_id if available, otherwise generate one
    # This ensures consistency across the call stack
    result_run_id = run_id if run_id else str(uuid4())

    return SimulationResult(
        run_id=result_run_id,
        trajectory=trajectory,
        steps=step_results,
        approved=approved,
        rejected_step_index=rejected_index,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_hash=policy_hash,
        planner_name=planner_name,
        planner_metadata=planner_metadata,
    )
