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
from services.core.market import MarketPath

BASE_DIR = ROOT
OUTPUTS_PATH = Path(os.environ.get("AWS_OUTPUTS_PATH", BASE_DIR / "infra" / "cdk" / "cdk-outputs.json"))
FIXTURE_PATH = BASE_DIR / "examples" / "fixtures" / "trading_path.json"


def invoke_lambda(function_name: str, payload: dict) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    return json.loads(response["Payload"].read().decode("utf-8"))


def _load_explanation(run_id: str, outputs: dict, rejected_step: int | None) -> str:
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
    if rejected_step is None:
        return steps[-1].get("explanation", "")
    if rejected_step < len(steps):
        return steps[rejected_step].get("explanation", "")
    return steps[-1].get("explanation", "")


def _print_plan(label: str, goal: str, response: dict, plan: list[dict], fixture: MarketPath, outputs: dict) -> None:
    print(f"\n{label}")
    print(f"Planner=mock goal={goal}")
    print("Plan:")
    for index, action in enumerate(plan):
        price_context = fixture.price_context(index)
        price = price_context.get(action["symbol"], action.get("price", 0.0))
        side = "BUY" if action["type"] == "PlaceBuy" else "SELL"
        print(f"  {index + 1}) {side} {action['quantity']} {action['symbol']} @ {price}")

    decision = "approved" if response.get("approved") else "rejected"
    run_id = response.get("run_id")
    explanation = _load_explanation(run_id, outputs, response.get("rejected_step_index")) if run_id else ""
    print(f"Decision: {decision} run_id={run_id}")
    print(f"Explanation: {explanation}")
    print(f"Artifacts: {response.get('artifact_s3_prefix')}")


def main() -> None:
    outputs = load_outputs(OUTPUTS_PATH)
    simulate_fn = outputs["SimulateFunctionName"]

    fixture = MarketPath.from_fixture(FIXTURE_PATH)

    reject_plan = [
        {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1},
        {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 20},
    ]
    approve_plan = [
        {"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1},
        {"type": "PlaceBuy", "symbol": "MSFT", "quantity": 1},
    ]

    reject_response = invoke_lambda(
        simulate_fn,
        {
            "mode": "planner",
            "planner": {"name": "mock", "goal": "reject", "note": ""},
            "state_id": "aws_planner_reject",
            "policy_id": "aws_planner_policy",
        },
    )
    if reject_response.get("planner_error"):
        print(json.dumps(reject_response, indent=2))
        return
    _print_plan(
        "AWS Planner Scenario A (expected rejection)",
        "reject",
        reject_response,
        reject_plan,
        fixture,
        outputs,
    )

    approve_response = invoke_lambda(
        simulate_fn,
        {
            "mode": "planner",
            "planner": {"name": "mock", "goal": "approve", "note": ""},
            "state_id": "aws_planner_approve",
            "policy_id": "aws_planner_policy",
        },
    )
    if approve_response.get("planner_error"):
        print(json.dumps(approve_response, indent=2))
        return
    _print_plan(
        "AWS Planner Scenario B (expected approval)",
        "approve",
        approve_response,
        approve_plan,
        fixture,
        outputs,
    )

    if os.environ.get("ENABLE_BEDROCK_PLANNER") == "1":
        print("\nNote: Bedrock planner is enabled; set planner.name=bedrock to test it.")
    else:
        print("\nNote: Bedrock planner is disabled by default; set ENABLE_BEDROCK_PLANNER=1 to enable.")


if __name__ == "__main__":
    main()