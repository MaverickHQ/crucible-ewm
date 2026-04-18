from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

import boto3

from services.aws.adapters.s3_writer import S3ArtifactWriter
from services.core.agentcore_tools import (
    Budget,
    ToolName,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    run_tool_loop,
)
from services.core.market import MarketPath
from services.core.simulator import simulate_plan
from services.core.state import RiskLimits, State
from services.core.strategy.evaluate import evaluate_signals_with_rationale, signals_to_actions
from services.core.strategy.load import load_strategy


def _artifact_keys(run_id: str) -> Dict[str, str]:
    prefix = f"artifacts/{run_id}"
    return {
        "artifact_prefix": prefix,
        "decision_key": f"{prefix}/decision.json",
        "report_key": f"{prefix}/report.md",
    }


def _load_fixture() -> MarketPath:
    fixture_name = os.environ.get("FIXTURE_NAME", "trading_path.json")
    fixture_path = Path(__file__).resolve().parents[1] / "assets" / "fixtures" / fixture_name
    if fixture_path.exists():
        return MarketPath.from_fixture(fixture_path)
    raise FileNotFoundError(f"Missing fixture: {fixture_name}")


def _default_state() -> State:
    return State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(
            max_leverage=2.0,
            max_position_pct=0.8,
            max_position_value=5_000.0,
        ),
    )


def _decision_payload(
    run_id: str,
    budget: Budget,
    budget_state: dict,
    tool_results: List[ToolResult],
    artifact_dir: str,
    ok: bool,
    errors: List[str],
) -> Dict[str, object]:
    return {
        "run_id": run_id,
        "mode": "agentcore-tools",
        "ok": ok,
        "budget": budget.model_dump(),
        "budget_state": budget_state,
        "tool_results": [result.model_dump() for result in tool_results],
        "errors": errors,
        "artifact_dir": artifact_dir,
    }


def _report_body(run_id: str, artifact_dir: str, tool_results: List[ToolResult]) -> str:
    lines = [
        "# AgentCore Tools Report",
        "",
        f"Run ID: {run_id}",
        f"Artifacts: {artifact_dir}",
        "",
        "## Tool Results",
    ]
    for index, result in enumerate(tool_results):
        status = "ok" if result.ok else "error"
        lines.append(f"- Step {index}: {status}")
        if result.error:
            lines.append(f"  - error: {result.error}")
    lines.extend(
        [
            "",
            "## Replay",
            "(placeholder)",
            "",
        ]
    )
    return "\n".join(lines)


def _compute_actions(
    fixture: MarketPath,
    strategy_path: str,
    step: int,
) -> List[Dict[str, Any]]:
    strategy = load_strategy(strategy_path)
    price_context = fixture.price_context(step)
    state = _default_state()
    evaluation = evaluate_signals_with_rationale(
        strategy=strategy,
        state=state,
        price_ctx=price_context,
        step_index=step,
        market_path=fixture,
    )
    actions = signals_to_actions(strategy, state, price_context, evaluation.signals)
    return [action.to_dict() for action in actions]


def _build_registry(
    fixture: MarketPath,
    bucket_name: str,
    strategy_path: str,
) -> ToolRegistry:
    registry = ToolRegistry()

    def get_price_context(request: ToolRequest) -> ToolResult:
        step = int(request.args.get("step", 0))
        price_context = fixture.price_context(step)
        return ToolResult(ok=True, output={"prices": price_context})

    def evaluate_strategy(request: ToolRequest) -> ToolResult:
        step = int(request.args.get("step", 0))
        strategy_file = request.args.get("strategy_path", strategy_path)
        serialized_actions = _compute_actions(fixture, strategy_file, step)
        strategy = load_strategy(strategy_file)
        price_context = fixture.price_context(step)
        state = _default_state()
        evaluation = evaluate_signals_with_rationale(
            strategy=strategy,
            state=state,
            price_ctx=price_context,
            step_index=step,
            market_path=fixture,
        )
        return ToolResult(
            ok=True,
            output={
                "signals": {key: value.value for key, value in evaluation.signals.items()},
                "actions": serialized_actions,
            },
        )

    def simulate_and_verify(request: ToolRequest) -> ToolResult:
        actions_payload = request.args.get("actions", [])
        actions = []
        for item in actions_payload:
            if item.get("type") == "PlaceBuy":
                from services.core.actions import PlaceBuy

                actions.append(PlaceBuy(item["symbol"], item["quantity"], 0.0))
            elif item.get("type") == "PlaceSell":
                from services.core.actions import PlaceSell

                actions.append(PlaceSell(item["symbol"], item["quantity"], 0.0))

        initial_state = _default_state()
        result = simulate_plan(initial_state, actions, fixture)
        writer = S3ArtifactWriter(bucket_name=bucket_name)
        artifacts = writer.write(result)
        return ToolResult(
            ok=True,
            output={
                "approved": result.approved,
                "explanation": result.steps[-1].explanation if result.steps else "",
                "violations": [
                    {"code": error.code, "message": error.message}
                    for step in result.steps
                    for error in step.errors
                ],
                "artifact_dir": f"s3://{bucket_name}/{artifacts['artifact_prefix']}",
                "run_id": result.run_id,
            },
        )

    registry.register(ToolName.GET_PRICE_CONTEXT, get_price_context)
    registry.register(ToolName.EVALUATE_STRATEGY, evaluate_strategy)
    registry.register(ToolName.SIMULATE_AND_VERIFY, simulate_and_verify)

    return registry


def _default_tool_plan(strategy_path: str) -> List[ToolRequest]:
    return [
        ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={"step": 0}),
        ToolRequest(
            name=ToolName.EVALUATE_STRATEGY,
            args={"strategy_path": strategy_path, "step": 0},
        ),
        ToolRequest(
            name=ToolName.SIMULATE_AND_VERIFY,
            args={"actions": [], "state_id": "current", "policy_id": "default"},
        ),
    ]


def _prepare_tool_plan(
    tool_plan: List[ToolRequest],
    strategy_path: str,
    fixture: MarketPath,
) -> List[ToolRequest]:
    prepared: List[ToolRequest] = []
    last_actions: List[Dict[str, Any]] = []

    for request in tool_plan:
        updated_request = request
        if request.name == ToolName.EVALUATE_STRATEGY:
            step = int(request.args.get("step", 0))
            strategy_file = request.args.get("strategy_path", strategy_path)
            last_actions = _compute_actions(fixture, strategy_file, step)
            if "strategy_path" not in request.args:
                updated_request = request.model_copy(
                    update={"args": {**request.args, "strategy_path": strategy_path}}
                )

        if request.name == ToolName.SIMULATE_AND_VERIFY:
            if "actions" not in request.args:
                updated_request = updated_request.model_copy(
                    update={"args": {**request.args, "actions": last_actions}}
                )

        prepared.append(updated_request)

    return prepared


def handler(event, context):
    payload = event if isinstance(event, dict) else json.loads(event)
    if payload.get("body"):
        payload = json.loads(payload["body"])

    bucket_name = os.environ["ARTIFACT_BUCKET"]
    run_id = str(uuid.uuid4())
    fixture = _load_fixture()

    strategy_path = payload.get("strategy_path", "examples/strategies/threshold_demo.json")

    budget_payload = payload.get("budget", {})
    budget = Budget(
        max_steps=int(budget_payload.get("max_steps", payload.get("max_steps", 5))),
        max_tool_calls=int(budget_payload.get("max_tool_calls", 5)),
        max_model_calls=int(budget_payload.get("max_model_calls", 0)),
        max_memory_ops=int(budget_payload.get("max_memory_ops", 0)),
        max_memory_bytes=int(budget_payload.get("max_memory_bytes", 0)),
    )

    tool_plan_payload = payload.get("tool_plan")
    if tool_plan_payload:
        tool_plan = [ToolRequest.model_validate(item) for item in tool_plan_payload]
    else:
        tool_plan = _default_tool_plan(strategy_path)

    registry = _build_registry(fixture, bucket_name, strategy_path)
    prepared_plan = _prepare_tool_plan(tool_plan, strategy_path, fixture)
    results, budget_state = run_tool_loop(prepared_plan, registry, budget)

    for request, result in zip(prepared_plan, results):
        if request.name == ToolName.SIMULATE_AND_VERIFY and result.ok:
            if not result.output.get("approved", True):
                result.ok = False
                result.error = "simulation rejected"
                break

    ok = all(result.ok for result in results)
    errors = [result.error for result in results if result.error]

    keys = _artifact_keys(run_id)
    artifact_dir = f"s3://{bucket_name}/{keys['artifact_prefix']}/"
    decision_payload = _decision_payload(
        run_id,
        budget,
        budget_state.model_dump(),
        results,
        artifact_dir,
        ok,
        errors,
    )

    report_body = _report_body(run_id, artifact_dir, results)
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["decision_key"],
        Body=json.dumps(decision_payload, indent=2).encode("utf-8"),
    )
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["report_key"],
        Body=report_body.encode("utf-8"),
    )

    response_payload = {
        "ok": ok,
        "run_id": run_id,
        "mode": "agentcore-tools",
        "artifact_dir": artifact_dir,
        "budget_state": budget_state.model_dump(),
    }

    if isinstance(event, dict) and event.get("requestContext", {}).get("http"):
        return {
            "statusCode": 200 if ok else 400,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(response_payload),
        }

    return response_payload
