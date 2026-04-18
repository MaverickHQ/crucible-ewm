from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

import boto3

from ewm_core.actions import PlaceBuy, PlaceSell
from ewm_core.simulator import SimulationResult, StepResult
from ewm_core.state import RiskLimits, State
from ewm_core.verifier import VerificationError


@dataclass
class DdbStateStore:
    table_name: str
    state_id: str = "current"

    def __post_init__(self) -> None:
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    def get_current_state(self) -> Optional[State]:
        response = self._table.get_item(Key={"state_id": self.state_id})
        item = response.get("Item")
        if not item:
            return None
        item = _from_ddb(item)
        risk_limits = item["risk_limits"]
        return State(
            cash_balance=item["cash_balance"],
            positions=item.get("positions", {}),
            exposure=item.get("exposure", 0.0),
            risk_limits=RiskLimits(
                max_leverage=risk_limits["max_leverage"],
                max_position_pct=risk_limits["max_position_pct"],
                max_position_value=risk_limits["max_position_value"],
            ),
        )

    def init_state(self, state: State) -> None:
        payload = _to_ddb(state.to_dict())
        payload["state_id"] = self.state_id
        self._table.put_item(Item=payload)

    def update_state(self, state: State) -> None:
        self.init_state(state)


@dataclass
class DdbRunStore:
    table_name: str

    def __post_init__(self) -> None:
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    def save_run(self, simulation_result: SimulationResult) -> None:
        payload = _serialize_simulation(simulation_result)
        payload["run_id"] = simulation_result.run_id
        self._table.put_item(Item=_to_ddb(payload))

    def get_run(self, run_id: str) -> Optional[SimulationResult]:
        response = self._table.get_item(Key={"run_id": run_id})
        item = response.get("Item")
        if not item:
            return None
        return _deserialize_simulation(_from_ddb(item))


@dataclass
class DdbPolicyStore:
    table_name: str

    def __post_init__(self) -> None:
        self._table = boto3.resource("dynamodb").Table(self.table_name)

    def save_policy(self, policy: dict) -> None:
        self._table.put_item(Item=_to_ddb(policy))

    def get_policy(self, policy_id: str) -> Optional[dict]:
        response = self._table.get_item(Key={"policy_id": policy_id})
        item = response.get("Item")
        return _from_ddb(item) if item else None


def _serialize_simulation(result: SimulationResult) -> Dict[str, object]:
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
    def action_from_payload(payload: dict):
        if payload["type"] == "PlaceBuy":
            return PlaceBuy(payload["symbol"], payload["quantity"], payload["price"])
        return PlaceSell(payload["symbol"], payload["quantity"], payload["price"])

    trajectory = [
        State(
            cash_balance=state["cash_balance"],
            positions=state.get("positions", {}),
            exposure=state.get("exposure", 0.0),
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
            action=action_from_payload(step["action"]),
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


def _to_ddb(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_ddb(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_ddb(item) for item in value]
    return value


def _from_ddb(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _from_ddb(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_from_ddb(item) for item in value]
    return value
