from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ewm_core.simulator import SimulationResult
from ewm_core.state import RiskLimits, State


@dataclass
class StateStore:
    state_path: Path

    def get_current_state(self) -> Optional[State]:
        if not self.state_path.exists():
            return None
        data = json.loads(self.state_path.read_text())
        risk_limits = data.get("risk_limits", {})
        return State(
            cash_balance=data["cash_balance"],
            positions=data["positions"],
            exposure=data["exposure"],
            risk_limits=RiskLimits(
                max_leverage=risk_limits["max_leverage"],
                max_position_pct=risk_limits["max_position_pct"],
                max_position_value=risk_limits["max_position_value"],
            ),
        )

    def init_state(self, state: State) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state.to_dict(), indent=2))

    def update_state(self, state: State) -> None:
        self.init_state(state)


@dataclass
class RunStore:
    runs_path: Path

    def save_run(self, simulation_result: SimulationResult) -> None:
        self.runs_path.parent.mkdir(parents=True, exist_ok=True)
        runs = self._load_runs()
        runs[simulation_result.run_id] = _serialize_simulation(simulation_result)
        self.runs_path.write_text(json.dumps(runs, indent=2))

    def get_run(self, run_id: str) -> Optional[SimulationResult]:
        runs = self._load_runs()
        data = runs.get(run_id)
        if not data:
            return None
        return _deserialize_simulation(data)

    def _load_runs(self) -> Dict[str, dict]:
        if not self.runs_path.exists():
            return {}
        return json.loads(self.runs_path.read_text())


@dataclass
class PolicyStore:
    policies_path: Path

    def save_policy(self, policy: dict) -> None:
        self.policies_path.parent.mkdir(parents=True, exist_ok=True)
        policies = self._load_policies()
        policies[policy["policy_id"]] = policy
        self.policies_path.write_text(json.dumps(policies, indent=2))

    def get_policy(self, policy_id: str) -> Optional[dict]:
        policies = self._load_policies()
        return policies.get(policy_id)

    def _load_policies(self) -> Dict[str, dict]:
        if not self.policies_path.exists():
            return {}
        return json.loads(self.policies_path.read_text())


def _serialize_simulation(result: SimulationResult) -> dict:
    return {
        "run_id": result.run_id,
        "approved": result.approved,
        "rejected_step_index": result.rejected_step_index,
        "planner": {
            "planner_name": result.planner_name,
            "planner_metadata": result.planner_metadata,
        },
        "policy": {
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
            "policy_hash": result.policy_hash,
        },
        "trajectory": [state.to_dict() for state in result.trajectory],
        "steps": [
            {
                "step_index": step.step_index,
                "action": {
                    "type": step.action.__class__.__name__,
                    "symbol": step.action.symbol,
                    "quantity": step.action.quantity,
                    "price": step.action.price,
                },
                "accepted": step.accepted,
                "errors": [{"code": error.code, "message": error.message} for error in step.errors],
                "price_context": step.price_context,
                "explanation": step.explanation,
                "state_delta": step.state_delta,
            }
            for step in result.steps
        ],
    }


def _deserialize_simulation(data: dict) -> SimulationResult:
    from ewm_core.actions import PlaceBuy, PlaceSell
    from ewm_core.simulator import SimulationResult, StepResult
    from ewm_core.verifier import VerificationError

    def _action_from_payload(payload: dict):
        action_type = payload["type"]
        if action_type == "PlaceBuy":
            return PlaceBuy(payload["symbol"], payload["quantity"], payload["price"])
        return PlaceSell(payload["symbol"], payload["quantity"], payload["price"])

    trajectory = [
        State(
            cash_balance=state["cash_balance"],
            positions=state["positions"],
            exposure=state["exposure"],
            risk_limits=RiskLimits(
                max_leverage=state["risk_limits"]["max_leverage"],
                max_position_pct=state["risk_limits"]["max_position_pct"],
                max_position_value=state["risk_limits"]["max_position_value"],
            ),
        )
        for state in data["trajectory"]
    ]

    steps = [
        StepResult(
            step_index=step["step_index"],
            action=_action_from_payload(step["action"]),
            accepted=step["accepted"],
            errors=[
                VerificationError(code=error["code"], message=error["message"])
                for error in step["errors"]
            ],
            price_context=step["price_context"],
            explanation=step.get("explanation", ""),
            state_delta=step.get("state_delta", {}),
        )
        for step in data["steps"]
    ]

    policy = data.get("policy", {})
    planner = data.get("planner", {})

    return SimulationResult(
        run_id=data["run_id"],
        trajectory=trajectory,
        steps=steps,
        approved=data["approved"],
        rejected_step_index=data.get("rejected_step_index"),
        policy_id=policy.get("policy_id"),
        policy_version=policy.get("policy_version"),
        policy_hash=policy.get("policy_hash"),
        planner_name=planner.get("planner_name"),
        planner_metadata=planner.get("planner_metadata"),
    )
