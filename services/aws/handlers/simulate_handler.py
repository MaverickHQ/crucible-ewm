from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from services.aws.adapters.ddb_stores import DdbPolicyStore, DdbRunStore, DdbStateStore
from services.aws.adapters.s3_writer import S3ArtifactWriter
from ewm_core.actions import PlaceBuy, PlaceSell
from ewm_core.market import MarketPath
from ewm_core.planner import BedrockPlanner, MockPlanner
from ewm_core.policy.versioning import ensure_policy_metadata
from ewm_core.simulator import simulate_plan
from ewm_core.state import RiskLimits, State


def _load_fixture() -> MarketPath:
    fixture_name = os.environ.get("FIXTURE_NAME", "trading_path.json")
    fixture_path = Path(__file__).resolve().parents[1] / "assets" / "fixtures" / fixture_name
    if fixture_path.exists():
        return MarketPath.from_fixture(fixture_path)

    fixture_payload = {
        "symbols": ["AAPL", "MSFT"],
        "steps": [
            {"AAPL": 100.0, "MSFT": 200.0},
            {"AAPL": 101.0, "MSFT": 198.0},
            {"AAPL": 99.5, "MSFT": 201.5},
            {"AAPL": 102.0, "MSFT": 203.0},
            {"AAPL": 101.5, "MSFT": 202.0},
        ],
    }
    return MarketPath(symbols=fixture_payload["symbols"], steps=fixture_payload["steps"])


def _actions_from_payload(actions_payload: List[Dict[str, Any]]):
    actions = []
    for item in actions_payload:
        if item["type"] == "PlaceBuy":
            actions.append(PlaceBuy(item["symbol"], item["quantity"], 0.0))
        elif item["type"] == "PlaceSell":
            actions.append(PlaceSell(item["symbol"], item["quantity"], 0.0))
    return actions


def _planner_error(code: str, message: str) -> Dict[str, object]:
    return {
        "planner_error": {"code": code, "message": message},
        "approved": False,
        "rejected_step_index": None,
        "errors_summary": [],
        "artifact_s3_prefix": None,
    }


def handler(event, context):
    payload = event if isinstance(event, dict) else json.loads(event)

    state_table = os.environ["STATE_TABLE"]
    runs_table = os.environ["RUNS_TABLE"]
    policies_table = os.environ["POLICIES_TABLE"]
    bucket_name = os.environ["ARTIFACT_BUCKET"]
    state_id = payload.get("state_id", "current")
    policy_id = payload.get("policy_id", "default")

    state_store = DdbStateStore(table_name=state_table, state_id=state_id)
    run_store = DdbRunStore(table_name=runs_table)
    policy_store = DdbPolicyStore(table_name=policies_table)
    artifact_writer = S3ArtifactWriter(bucket_name=bucket_name)

    fixture = _load_fixture()

    planner_payload = payload.get("planner", {}) if isinstance(payload, dict) else {}

    initial_state = state_store.get_current_state()
    if payload.get("initial_state"):
        override = payload["initial_state"]
        initial_state = State(
            cash_balance=override["cash_balance"],
            positions=override.get("positions", {}),
            exposure=override.get("exposure", 0.0),
            risk_limits=RiskLimits(
                max_leverage=override["risk_limits"]["max_leverage"],
                max_position_pct=override["risk_limits"]["max_position_pct"],
                max_position_value=override["risk_limits"]["max_position_value"],
            ),
        )

    policy = policy_store.get_policy(policy_id)
    if policy:
        policy = ensure_policy_metadata(policy)
    if initial_state is None:
        policy = policy or ensure_policy_metadata(
            {
                "policy_id": policy_id,
                "risk_limits": {
                    "max_leverage": 2.0,
                    "max_position_pct": 0.8,
                    "max_position_value": 5_000.0,
                },
            }
        )
        limits = policy["risk_limits"]
        initial_state = State(
            cash_balance=1_000.0,
            positions={},
            exposure=0.0,
            risk_limits=RiskLimits(
                limits["max_leverage"],
                limits["max_position_pct"],
                limits["max_position_value"],
            ),
        )
        state_store.init_state(initial_state)

    if policy is None:
        policy = ensure_policy_metadata(
            {
                "policy_id": policy_id,
                "risk_limits": {
                    "max_leverage": 2.0,
                    "max_position_pct": 0.8,
                    "max_position_value": 5_000.0,
                },
            }
        )

    mode = payload.get("mode", "direct")
    planner_name = planner_payload.get("planner_name") or planner_payload.get("name")
    planner_metadata = planner_payload.get("planner_metadata")

    if mode == "planner":
        planner_name = planner_payload.get("name", "mock")
        goal = planner_payload.get("goal", "approve")
        note = planner_payload.get("note", "")

        if planner_name == "mock":
            planner = MockPlanner()
        elif planner_name == "bedrock":
            if os.environ.get("ENABLE_BEDROCK_PLANNER") != "1":
                return _planner_error(
                    "planner_disabled",
                    "Bedrock planner is disabled. Set ENABLE_BEDROCK_PLANNER=1.",
                )
            model_id = os.environ.get("BEDROCK_MODEL_ID", "")
            if not model_id:
                return _planner_error(
                    "planner_config_missing",
                    "BEDROCK_MODEL_ID is not set.",
                )
            region = os.environ.get("AWS_REGION", "us-east-1")
            planner = BedrockPlanner(model_id=model_id, region_name=region)
        else:
            return _planner_error("planner_unknown", f"Unknown planner: {planner_name}")

        planner_result = planner.propose(initial_state.to_dict(), policy, goal)
        if planner_result.error:
            return _planner_error(planner_result.error.code, planner_result.error.message)
        if note:
            planner_result.metadata["note"] = note
        planner_name = planner_result.planner_name
        planner_metadata = planner_result.metadata
        actions = planner_result.plan
    else:
        if "scenario" in payload:
            scenario_path = (
                Path(__file__).resolve().parents[1] / "assets" / "scenarios" / payload["scenario"]
            )
            scenario_payload = json.loads(scenario_path.read_text())
            actions = _actions_from_payload(scenario_payload["plan"])
        else:
            actions = _actions_from_payload(payload.get("plan", []))
        if planner_metadata is None and planner_payload:
            planner_metadata = {
                key: value for key, value in planner_payload.items() if key != "name"
            }

    result = simulate_plan(
        initial_state,
        actions,
        fixture,
        policy_id=policy.get("policy_id"),
        policy_version=policy.get("policy_version"),
        policy_hash=policy.get("policy_hash"),
        planner_name=planner_name,
        planner_metadata=planner_metadata,
    )
    run_store.save_run(result)
    artifacts = artifact_writer.write(result)

    errors_summary = [
        {
            "step_index": step.step_index,
            "errors": [{"code": error.code, "message": error.message} for error in step.errors],
        }
        for step in result.steps
        if step.errors
    ]

    return {
        "run_id": result.run_id,
        "approved": result.approved,
        "rejected_step_index": result.rejected_step_index,
        "errors_summary": errors_summary,
        "artifact_s3_prefix": f"s3://{bucket_name}/{artifacts['artifact_prefix']}",
    }
