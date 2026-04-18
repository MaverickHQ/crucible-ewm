from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import boto3
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ewm_core.agentcore_memory import (
    BedrockAgentCoreMemoryStore,
    DynamoDBMemoryStore,
    InMemoryMemoryStore,
    MemoryStore,
    MemoryStoreError,
    NoOpMemoryStore,
)
from ewm_core.agentcore_memory.store import estimate_memory_bytes
from ewm_core.agentcore_tools import Budget, BudgetState


class MemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: str
    key: str
    value: Optional[Dict[str, Any]] = None


class MemoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentcore-memory"
    budget: Dict[str, int] = Field(default_factory=dict)
    requests: Optional[list[MemoryRequest]] = None


def _artifact_keys(run_id: str) -> Dict[str, str]:
    prefix = f"artifacts/{run_id}"
    return {
        "artifact_prefix": prefix,
        "decision_key": f"{prefix}/decision.json",
        "report_key": f"{prefix}/report.md",
        "budgets_key": f"{prefix}/budgets.json",
        "memory_key": f"{prefix}/memory.json",
    }


def _default_requests(run_id: str) -> list[MemoryRequest]:
    payload = {"run_id": run_id, "note": "hello-memory"}
    return [
        MemoryRequest(op="memory_put", key="last_run", value=payload),
        MemoryRequest(op="memory_get", key="last_run"),
    ]


def _build_budget(payload: MemoryPayload) -> Budget:
    budget_payload = payload.budget
    return Budget(
        max_steps=int(budget_payload.get("max_steps", 1)),
        max_tool_calls=int(budget_payload.get("max_tool_calls", 0)),
        max_model_calls=int(budget_payload.get("max_model_calls", 0)),
        max_memory_ops=int(budget_payload.get("max_memory_ops", 1)),
        max_memory_bytes=int(budget_payload.get("max_memory_bytes", 512)),
    )


def _budget_exceeded_response(
    run_id: str,
    bucket_name: str,
    keys: Dict[str, str],
    budget: Budget,
    state: BudgetState,
    limiter: str,
    message: str,
    memory_enabled: bool,
) -> Dict[str, Any]:
    decision_payload = {
        "run_id": run_id,
        "mode": "agentcore-memory",
        "ok": False,
        "error": {
            "code": "budget_exceeded",
            "limiter": limiter,
            "message": message,
            "budgets": {"budget": budget.model_dump(), "budget_state": state.model_dump()},
        },
        "memory_enabled": memory_enabled,
        "budget": budget.model_dump(),
        "budget_state": state.model_dump(),
        "memory": {"ops": []},
        "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
    }
    report_body = _report_body(run_id, bucket_name, keys["artifact_prefix"], decision_payload)
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
    budgets_payload = {"budget": budget.model_dump(), "budget_state": state.model_dump()}
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["budgets_key"],
        Body=json.dumps(budgets_payload, indent=2).encode("utf-8"),
    )
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["memory_key"],
        Body=json.dumps({"ops": []}, indent=2).encode("utf-8"),
    )
    return {
        "ok": False,
        "run_id": run_id,
        "mode": "agentcore-memory",
        "error": {
            "code": "budget_exceeded",
            "limiter": limiter,
            "message": message,
            "budgets": {"budget": budget.model_dump(), "budget_state": state.model_dump()},
        },
        "memory_enabled": memory_enabled,
        "memory": {"ops": []},
        "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
        "budget": budget.model_dump(),
        "budget_state": state.model_dump(),
    }


def _report_body(
    run_id: str, bucket_name: str, artifact_prefix: str, decision_payload: Dict[str, Any]
) -> str:
    return "\n".join(
        [
            "# AgentCore Memory Report",
            "",
            f"Run ID: {run_id}",
            f"Artifacts: s3://{bucket_name}/{artifact_prefix}/",
            "",
            "## Summary",
            json.dumps(
                {
                    "ok": decision_payload.get("ok"),
                    "budget": decision_payload.get("budget"),
                    "budget_state": decision_payload.get("budget_state"),
                },
                indent=2,
                sort_keys=True,
            ),
            "",
            "## Replay",
            "(placeholder)",
            "",
        ]
    )


def _resolve_store() -> Tuple[MemoryStore, str, bool, bool, Optional[str]]:
    if os.environ.get("ENABLE_AGENTCORE_MEMORY") != "1":
        return NoOpMemoryStore(), "disabled", False, True, None
    store_kind = os.environ.get("AGENTCORE_MEMORY_BACKEND", "in-memory")
    try:
        if store_kind == "dynamodb":
            return (
                DynamoDBMemoryStore(
                    table_name=os.environ.get("AGENTCORE_MEMORY_TABLE", ""),
                    ttl_seconds=int(os.environ.get("AGENTCORE_MEMORY_TTL_SECONDS", "86400")),
                ),
                "dynamodb",
                True,
                True,
                None,
            )
        if store_kind == "agentcore":
            return BedrockAgentCoreMemoryStore(), "agentcore", True, True, None
        return InMemoryMemoryStore(storage={}), "in-memory", True, True, None
    except Exception as exc:  # pragma: no cover - defensive init guard
        return NoOpMemoryStore(), store_kind, True, False, str(exc)


def _precheck_budget(requests: list[MemoryRequest], budget: Budget) -> Optional[Dict[str, str]]:
    total_ops = len(requests)
    if total_ops > budget.max_memory_ops:
        return {
            "code": "budget_exceeded",
            "limiter": "max_memory_ops",
            "message": "budget exceeded: max_memory_ops",
        }

    total_bytes = 0
    for request in requests:
        payload = {"op": request.op, "key": request.key, "value": request.value}
        total_bytes += estimate_memory_bytes(payload)

    if total_bytes > budget.max_memory_bytes:
        return {
            "code": "budget_exceeded",
            "limiter": "max_memory_bytes",
            "message": "budget exceeded: max_memory_bytes",
        }

    return None


def _record_memory_op(state: BudgetState, payload: Dict[str, Any], budget: Budget) -> Optional[str]:
    state.increment_memory_ops()
    state.increment_memory_bytes(estimate_memory_bytes(payload))
    if state.memory_ops > budget.max_memory_ops:
        return "max_memory_ops"
    if state.memory_bytes > budget.max_memory_bytes:
        return "max_memory_bytes"
    return None


def _execute_requests(
    store: MemoryStore,
    budget: Budget,
    state: BudgetState,
    requests: list[MemoryRequest],
) -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
    memory_trace: Dict[str, Any] = {"ops": []}
    for request in requests:
        payload = {"op": request.op, "key": request.key, "value": request.value}
        limiter = _record_memory_op(state, payload, budget)
        if limiter:
            return memory_trace, {
                "code": "budget_exceeded",
                "limiter": limiter,
                "message": f"budget exceeded: {limiter}",
            }

        if request.op == "memory_put":
            if request.value is None:
                return memory_trace, {
                    "code": "invalid_request",
                    "message": "memory_put requires value",
                }
            store.put(request.key, request.value)
            memory_trace["ops"].append({"op": request.op, "key": request.key, "ok": True})
        elif request.op == "memory_get":
            value = store.get(request.key)
            memory_trace["ops"].append(
                {"op": request.op, "key": request.key, "value": value, "ok": True}
            )
        elif request.op == "memory_clear":
            store.put(request.key, {})
            memory_trace["ops"].append({"op": request.op, "key": request.key, "ok": True})
        else:
            return memory_trace, {
                "code": "invalid_request",
                "message": f"unsupported op: {request.op}",
            }

    return memory_trace, None


def handler(event, context):
    payload_data = event if isinstance(event, dict) else json.loads(event)
    if payload_data.get("body"):
        payload_data = json.loads(payload_data["body"])

    bucket_name = os.environ["ARTIFACT_BUCKET"]
    run_id = str(uuid.uuid4())
    keys = _artifact_keys(run_id)

    try:
        payload = MemoryPayload.model_validate(payload_data)
    except ValidationError as exc:
        return {
            "ok": False,
            "mode": "agentcore-memory",
            "error": {"code": "invalid_request", "message": exc.errors()},
        }

    budget = _build_budget(payload)
    state = BudgetState()
    requests = payload.requests or _default_requests(run_id)
    memory_enabled = os.environ.get("ENABLE_AGENTCORE_MEMORY") == "1"

    precheck_error = _precheck_budget(requests, budget) if memory_enabled else None
    if precheck_error:
        response_payload = _budget_exceeded_response(
            run_id,
            bucket_name,
            keys,
            budget,
            state,
            precheck_error.get("limiter", "max_memory_ops"),
            precheck_error.get("message", "budget exceeded"),
            memory_enabled,
        )
        if isinstance(event, dict) and event.get("requestContext", {}).get("http"):
            return {
                "statusCode": 400,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(response_payload),
            }
        return response_payload

    store, store_kind, memory_enabled, store_init_ok, store_init_error = _resolve_store()

    print(
        "agentcore_memory config "
        + json.dumps(
            {
                "memory_enabled": memory_enabled,
                "memory_backend": store_kind,
                "store_init_ok": store_init_ok,
                "budget": budget.model_dump(),
            },
            sort_keys=True,
        )
    )

    if store_kind == "disabled":
        decision_payload = {
            "run_id": run_id,
            "mode": "agentcore-memory",
            "ok": True,
            "message": "memory disabled",
            "memory_enabled": memory_enabled,
            "budget": budget.model_dump(),
            "budget_state": state.model_dump(),
            "memory": {"ops": []},
            "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
        }
        report_body = _report_body(run_id, bucket_name, keys["artifact_prefix"], decision_payload)
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
        budgets_payload = {"budget": budget.model_dump(), "budget_state": state.model_dump()}
        s3.put_object(
            Bucket=bucket_name,
            Key=keys["budgets_key"],
            Body=json.dumps(budgets_payload, indent=2).encode("utf-8"),
        )
        s3.put_object(
            Bucket=bucket_name,
            Key=keys["memory_key"],
            Body=json.dumps({"ops": []}, indent=2).encode("utf-8"),
        )

        response_payload = {
            "ok": True,
            "run_id": run_id,
            "mode": "agentcore-memory",
            "message": "memory disabled",
            "memory_enabled": memory_enabled,
            "store_init_ok": store_init_ok,
            "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
            "budget": budget.model_dump(),
            "budget_state": state.model_dump(),
        }
        if store_init_error:
            response_payload["store_init_error"] = store_init_error
        if isinstance(event, dict) and event.get("requestContext", {}).get("http"):
            return {
                "statusCode": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps(response_payload),
            }
        return response_payload

    try:
        memory_trace, error = _execute_requests(store, budget, state, requests)
    except MemoryStoreError as exc:
        error = {"code": exc.code, "message": str(exc)}
        memory_trace = {"ops": []}

    if error and error.get("code") == "budget_exceeded":
        response_payload = _budget_exceeded_response(
            run_id,
            bucket_name,
            keys,
            budget,
            state,
            error.get("limiter", "max_memory_ops"),
            error.get("message", "budget exceeded"),
            memory_enabled,
        )
    else:
        decision_payload = {
            "run_id": run_id,
            "mode": "agentcore-memory",
            "ok": error is None,
            "error": error,
            "memory_enabled": memory_enabled,
            "budget": budget.model_dump(),
            "budget_state": state.model_dump(),
            "memory": memory_trace,
            "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
        }
        report_body = _report_body(run_id, bucket_name, keys["artifact_prefix"], decision_payload)
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
        budgets_payload = {"budget": budget.model_dump(), "budget_state": state.model_dump()}
        s3.put_object(
            Bucket=bucket_name,
            Key=keys["budgets_key"],
            Body=json.dumps(budgets_payload, indent=2).encode("utf-8"),
        )
        s3.put_object(
            Bucket=bucket_name,
            Key=keys["memory_key"],
            Body=json.dumps(memory_trace, indent=2).encode("utf-8"),
        )

        response_payload = {
            "ok": error is None,
            "run_id": run_id,
            "mode": "agentcore-memory",
            "memory_enabled": memory_enabled,
            "store_init_ok": store_init_ok,
            "artifact_dir": f"s3://{bucket_name}/{keys['artifact_prefix']}/",
            "budget": budget.model_dump(),
            "budget_state": state.model_dump(),
            "memory": memory_trace,
        }
        if error:
            response_payload["error"] = error
        if store_init_error:
            response_payload["store_init_error"] = store_init_error

    if isinstance(event, dict) and event.get("requestContext", {}).get("http"):
        return {
            "statusCode": 200 if response_payload.get("ok") else 400,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(response_payload),
        }

    return response_payload
