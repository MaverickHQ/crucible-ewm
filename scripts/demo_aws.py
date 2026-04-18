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
SCENARIO_DIR = BASE_DIR / "examples" / "scenarios"


def invoke_lambda(function_name: str, payload: dict) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(response["Payload"].read().decode("utf-8"))


def _get_step_explanation(simulation_response: dict, outputs: dict) -> str:
    run_id = simulation_response.get("run_id")
    if not run_id:
        return ""

    bucket_name = outputs.get("ArtifactsBucketName")
    if not bucket_name:
        return ""

    s3 = boto3.client("s3")
    key = f"artifacts/{run_id}/trajectory.json"
    obj = s3.get_object(Bucket=bucket_name, Key=key)
    payload = json.loads(obj["Body"].read().decode("utf-8"))
    steps = payload.get("steps", [])
    if not steps:
        return ""
    rejected_step = simulation_response.get("rejected_step_index")
    if rejected_step is None:
        return steps[-1].get("explanation", "")
    return steps[rejected_step].get("explanation", "")


def main() -> None:
    outputs = load_outputs(OUTPUTS_PATH)

    simulate_fn = outputs["SimulateFunctionName"]
    execute_fn = outputs["ExecuteFunctionName"]

    print("Scenario A (expected rejection)")
    reject_response = invoke_lambda(
        simulate_fn,
        {
            "scenario": "scenario_reject.json",
            "state_id": "demo_scenario_a",
            "policy_id": "demo_policy_a",
        },
    )
    if "run_id" not in reject_response:
        print("Simulate response did not include run_id. Raw response:")
        print(json.dumps(reject_response, indent=2))
        return
    explanation = _get_step_explanation(reject_response, outputs)
    print(
        json.dumps(
            {
                "run_id": reject_response["run_id"],
                "approved": reject_response["approved"],
                "rejected_step_index": reject_response["rejected_step_index"],
                "errors_summary": reject_response.get("errors_summary", []),
                "artifact_s3_prefix": reject_response.get("artifact_s3_prefix"),
                "explanation": explanation,
            },
            indent=2,
        )
    )

    print("\nScenario B (expected approval)")
    approve_response = invoke_lambda(
        simulate_fn,
        {
            "scenario": "scenario_approve.json",
            "state_id": "demo_scenario_b",
            "policy_id": "demo_policy_b",
        },
    )
    if "run_id" not in approve_response:
        print("Simulate response did not include run_id. Raw response:")
        print(json.dumps(approve_response, indent=2))
        return
    explanation = _get_step_explanation(approve_response, outputs)
    print(
        json.dumps(
            {
                "run_id": approve_response["run_id"],
                "approved": approve_response["approved"],
                "rejected_step_index": approve_response["rejected_step_index"],
                "artifact_s3_prefix": approve_response.get("artifact_s3_prefix"),
                "explanation": explanation,
            },
            indent=2,
        )
    )

    execution = invoke_lambda(execute_fn, {"run_id": approve_response["run_id"]})
    print("\nExecution summary")
    print(
        json.dumps(
            {
                "run_id": execution["run_id"],
                "executed": execution["executed"],
                "state_summary": execution.get("state_summary"),
            },
            indent=2,
        )
    )

    print("\nPlanner demo (mock planner, expected rejection)")
    planner_response = invoke_lambda(
        simulate_fn,
        {
            "plan": [
                {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1},
                {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 20},
            ],
            "state_id": "demo_planner_a",
            "policy_id": "demo_policy_planner",
            "planner": {
                "planner_name": "mock",
                "planner_metadata": {"goal": "reject"},
            },
        },
    )
    if "run_id" in planner_response:
        explanation = _get_step_explanation(planner_response, outputs)
        print(
            json.dumps(
                {
                    "run_id": planner_response["run_id"],
                    "approved": planner_response["approved"],
                    "rejected_step_index": planner_response["rejected_step_index"],
                    "artifact_s3_prefix": planner_response.get("artifact_s3_prefix"),
                    "explanation": explanation,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
