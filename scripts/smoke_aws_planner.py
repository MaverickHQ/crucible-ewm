from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3

from services.aws.utils.output_loader import load_outputs

BASE_DIR = ROOT
OUTPUTS_PATH = Path(os.environ.get("AWS_OUTPUTS_PATH", BASE_DIR / "infra" / "cdk" / "cdk-outputs.json"))


def _invoke_lambda(function_name: str, payload: dict) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(response["Payload"].read().decode("utf-8"))


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


def _load_decision_planner(outputs: dict, run_id: str) -> dict:
    bucket = _get_bucket(outputs)
    key = f"artifacts/{run_id}/decision.json"
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    payload = json.loads(response["Body"].read().decode("utf-8"))
    return payload.get("planner", {})


def main() -> None:
    outputs = load_outputs(OUTPUTS_PATH)
    simulate_fn = outputs["SimulateFunctionName"]

    response = _invoke_lambda(
        simulate_fn,
        {
            "mode": "planner",
            "planner": {"name": "mock", "goal": "approve", "note": ""},
            "state_id": "smoke_planner_approve",
            "policy_id": "smoke_planner_policy",
        },
    )

    if response.get("planner_error"):
        raise AssertionError(response["planner_error"])
    if not response.get("approved"):
        raise AssertionError("Planner approval scenario was not approved.")

    run_id = response.get("run_id")
    planner = _load_decision_planner(outputs, run_id)
    if not planner.get("planner_name"):
        raise AssertionError("Planner name missing from decision artifact.")
    if not planner.get("planner_metadata"):
        raise AssertionError("Planner metadata missing from decision artifact.")

    _artifact_exists(outputs, run_id, "deltas.json")
    print(json.dumps({"approved": response.get("approved"), "run_id": run_id}, indent=2))


if __name__ == "__main__":
    main()