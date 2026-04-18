import json
import os
from pathlib import Path

import boto3
import pytest

from services.aws.utils.output_loader import load_outputs

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AWS_TESTS") != "1",
    reason="AWS tests are disabled by default.",
)


def _invoke_lambda(function_name: str, payload: dict) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(response["Payload"].read().decode("utf-8"))


def test_aws_demo_scenarios():
    outputs_path = Path(os.getenv("AWS_OUTPUTS_PATH", "infra/cdk/cdk-outputs.json"))
    outputs = load_outputs(outputs_path)

    simulate_fn = outputs["SimulateFunctionName"]
    execute_fn = outputs["ExecuteFunctionName"]

    reject_payload = {
        "scenario": "scenario_reject.json",
        "state_id": "test_scenario_a",
        "policy_id": "test_policy_a",
    }
    approve_payload = {
        "scenario": "scenario_approve.json",
        "state_id": "test_scenario_b",
        "policy_id": "test_policy_b",
    }

    reject_response = _invoke_lambda(simulate_fn, reject_payload)
    assert reject_response["approved"] is False
    assert reject_response["rejected_step_index"] is not None
    assert _load_decision_policy_hash(outputs, reject_response["run_id"])
    assert _artifact_exists(outputs, reject_response["run_id"], "deltas.json")

    approve_response = _invoke_lambda(simulate_fn, approve_payload)
    assert approve_response["approved"] is True
    assert approve_response["rejected_step_index"] is None
    assert _load_decision_policy_hash(outputs, approve_response["run_id"])
    assert _artifact_exists(outputs, approve_response["run_id"], "deltas.json")

    execution = _invoke_lambda(execute_fn, {"run_id": approve_response["run_id"]})
    assert execution["executed"] is True

    planner_response = _invoke_lambda(
        simulate_fn,
        {
            "plan": [
                {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1},
                {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 20},
            ],
            "state_id": "planner_scenario",
            "policy_id": "planner_policy",
            "planner": {"planner_name": "mock", "planner_metadata": {"goal": "reject"}},
        },
    )
    assert planner_response["approved"] is False
    assert _load_decision_planner_name(outputs, planner_response["run_id"]) == "mock"

    planner_reject = _invoke_lambda(
        simulate_fn,
        {
            "mode": "planner",
            "planner": {"name": "mock", "goal": "reject", "note": ""},
            "state_id": "planner_mode_reject",
            "policy_id": "planner_mode_policy",
        },
    )
    assert planner_reject["approved"] is False
    assert planner_reject["rejected_step_index"] is not None
    planner_name = _load_decision_planner_name(outputs, planner_reject["run_id"])
    assert planner_name == "mock"
    planner_metadata = _load_decision_planner_metadata(outputs, planner_reject["run_id"])
    assert planner_metadata
    assert _load_decision_policy_hash(outputs, planner_reject["run_id"])
    assert _artifact_exists(outputs, planner_reject["run_id"], "deltas.json")

    planner_approve = _invoke_lambda(
        simulate_fn,
        {
            "mode": "planner",
            "planner": {"name": "mock", "goal": "approve", "note": ""},
            "state_id": "planner_mode_approve",
            "policy_id": "planner_mode_policy",
        },
    )
    assert planner_approve["approved"] is True
    assert planner_approve["rejected_step_index"] is None
    planner_name = _load_decision_planner_name(outputs, planner_approve["run_id"])
    assert planner_name == "mock"
    planner_metadata = _load_decision_planner_metadata(outputs, planner_approve["run_id"])
    assert planner_metadata
    assert _load_decision_policy_hash(outputs, planner_approve["run_id"])
    assert _artifact_exists(outputs, planner_approve["run_id"], "deltas.json")

    execution = _invoke_lambda(execute_fn, {"run_id": planner_approve["run_id"]})
    assert execution["executed"] is True


def _s3_client():
    return boto3.client("s3")


def _get_bucket(outputs: dict) -> str:
    bucket = outputs.get("ArtifactsBucketName")
    if not bucket:
        raise AssertionError("Artifacts bucket not found in outputs.")
    return bucket


def _artifact_exists(outputs: dict, run_id: str, name: str) -> bool:
    bucket = _get_bucket(outputs)
    key = f"artifacts/{run_id}/{name}"
    _s3_client().head_object(Bucket=bucket, Key=key)
    return True


def _load_decision_policy_hash(outputs: dict, run_id: str) -> str:
    bucket = _get_bucket(outputs)
    key = f"artifacts/{run_id}/decision.json"
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    payload = json.loads(response["Body"].read().decode("utf-8"))
    policy = payload.get("policy", {})
    return policy.get("policy_hash", "")


def _load_decision_planner_name(outputs: dict, run_id: str) -> str:
    bucket = _get_bucket(outputs)
    key = f"artifacts/{run_id}/decision.json"
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    payload = json.loads(response["Body"].read().decode("utf-8"))
    planner = payload.get("planner", {})
    return planner.get("planner_name", "")


def _load_decision_planner_metadata(outputs: dict, run_id: str) -> dict:
    bucket = _get_bucket(outputs)
    key = f"artifacts/{run_id}/decision.json"
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    payload = json.loads(response["Body"].read().decode("utf-8"))
    planner = payload.get("planner", {})
    return planner.get("planner_metadata", {})
