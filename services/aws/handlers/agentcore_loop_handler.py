from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ewm_core.agentcore_loop.run import run_agentcore_loop
from ewm_core.agentcore_loop.types import LoopBudgets, LoopRequest
from ewm_core.persistence.runs_dynamo import put_run

NAMESPACE = "BeyondTokens/AgentCoreLoop"
SERVICE = "beyond-tokens"
COMPONENT = "agentcore-loop"


def _trace_id(event: dict[str, Any]) -> str:
    """
    Get correlation ID from request.
    Priority: x-correlation-id (case-insensitive) > x-amzn-trace-id > _X_AMZN_TRACE_ID env > UUID
    """
    from uuid import uuid4

    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        # Check all common header case variations
        for key in headers.keys() if isinstance(headers, dict) else []:
            key_lower = key.lower()
            if key_lower == "x-correlation-id":
                return headers[key]

    # Check case-insensitive for x-correlation-id
    if isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() == "x-correlation-id" and value:
                return value

    # Fall back to x-amzn-trace-id
    if isinstance(headers, dict):
        trace_id = (
            headers.get("x-amzn-trace-id")
            or headers.get("X-Amzn-Trace-Id")
            or os.environ.get("_X_AMZN_TRACE_ID", "")
        )
        if trace_id:
            return trace_id

    # Final fallback: generate UUID
    return str(uuid4())


def _log_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":"), default=str))


def _emit_emf_metrics(
    *,
    request_id: str,
    correlation_id: str,
    mode: str,
    http_status: int,
    duration_ms: int,
) -> None:
    client_errors = 1 if 400 <= http_status < 500 else 0
    server_errors = 1 if http_status >= 500 else 0
    _log_json(
        {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": NAMESPACE,
                        "Dimensions": [["service", "component", "mode"]],
                        "Metrics": [
                            {"Name": "Requests", "Unit": "Count"},
                            {"Name": "ClientErrors", "Unit": "Count"},
                            {"Name": "ServerErrors", "Unit": "Count"},
                            {"Name": "LatencyMs", "Unit": "Milliseconds"},
                        ],
                    }
                ],
            },
            "service": SERVICE,
            "component": COMPONENT,
            "mode": mode,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "Requests": 1,
            "ClientErrors": client_errors,
            "ServerErrors": server_errors,
            "LatencyMs": duration_ms,
        }
    )


def _parse(event: dict[str, Any]) -> LoopRequest:
    body_raw = event.get("body") or "{}"
    if isinstance(body_raw, str):
        body = json.loads(body_raw or "{}")
    else:
        body = body_raw

    # Support both legacy "budgets" and canonical "runtime_budgets" fields
    # Prefer runtime_budgets (v2 canonical), fall back to budgets (legacy)
    runtime_budgets = body.get("runtime_budgets") or body.get("budgets") or {}
    strategy_path = body.get("strategy_path")
    upload_s3 = body.get("upload_s3", True)
    # Generate run_id at the outermost boundary for consistency
    # This ensures run_id is the same across API response, S3 artifacts, and DynamoDB
    run_id = str(uuid4())
    return LoopRequest(
        budgets=LoopBudgets(
            max_steps=int(runtime_budgets.get("max_steps", 5)),
            max_tool_calls=int(runtime_budgets.get("max_tool_calls", 10)),
            max_model_calls=int(runtime_budgets.get("max_model_calls", 0)),
            max_memory_ops=int(runtime_budgets.get("max_memory_ops", 0)),
            max_memory_bytes=int(runtime_budgets.get("max_memory_bytes", 0)),
        ),
        seed=int(body.get("seed", 7)),
        symbols=tuple(body.get("symbols", ["AAPL", "MSFT"])),
        starting_cash=float(body.get("starting_cash", 1000.0)),
        steps=int(body.get("steps", 5)),
        write_artifacts=bool(body.get("write_artifacts", True)),
        upload_s3=bool(upload_s3),
        mode=str(body.get("mode", "agentcore-loop")),
        strategy_path=str(strategy_path) if strategy_path else None,
        run_id=run_id,
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    started = time.perf_counter()
    request_id = getattr(context, "aws_request_id", "") if context is not None else ""
    trace_id = _trace_id(event)

    req: LoopRequest | None = None
    try:
        req = _parse(event)
        result = run_agentcore_loop(req)
        status = 200 if result.get("ok") else 400
    except Exception as exc:
        req = req or LoopRequest(budgets=LoopBudgets())
        err = "internal_error"
        if isinstance(exc, RuntimeError):
            msg = str(exc)
            if msg == "artifact_upload_failed":
                err = "artifact_upload_failed"
            elif msg == "run_record_write_failed":
                err = "run_record_write_failed"
            elif msg == "persistence_config_missing":
                err = "persistence_config_missing"
        result = {
            "ok": False,
            "run_id": str(uuid4()),
            "mode": req.mode,
            "error": {"code": err, "message": "Internal Server Error"},
        }
        status = 500

    duration_ms = int((time.perf_counter() - started) * 1000)

    budgets_summary = {
        "max_steps": req.budgets.max_steps,
        "max_tool_calls": req.budgets.max_tool_calls,
        "max_model_calls": req.budgets.max_model_calls,
        "max_memory_ops": req.budgets.max_memory_ops,
        "max_memory_bytes": req.budgets.max_memory_bytes,
    }
    # Grep-friendly log line for correlation tracking
    print(f"correlation_id={trace_id}")

    _log_json(
        {
            "service": SERVICE,
            "component": COMPONENT,
            "mode": req.mode,
            "request_id": request_id,
            "correlation_id": trace_id,
            "http_status": status,
            "duration_ms": duration_ms,
            "steps": req.steps,
            "symbols": list(req.symbols),
            "budgets_summary": budgets_summary,
            "ok": bool(result.get("ok")),
        }
    )
    _emit_emf_metrics(
        request_id=request_id,
        correlation_id=trace_id,
        mode=req.mode,
        http_status=status,
        duration_ms=duration_ms,
    )

    runs_table = os.environ.get("RUNS_TABLE", "")
    if runs_table:
        run_record = {
            "run_id": result.get("run_id") or str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": req.mode,
            "symbols": list(req.symbols),
            "steps": req.steps,
            "ok": bool(result.get("ok")),
            "http_status": status,
            "duration_ms": duration_ms,
            "final_state": result.get("final_state"),
            "artifact_dir": result.get("artifact_dir"),
            "error": result.get("error"),
            # Canonical field: correlation_id (matches API response/logs/EMF)
            "correlation_id": trace_id,
            # DEPRECATED: trace_id retained for backward compatibility.
            # Prefer correlation_id for new integrations; trace_id will be
            # removed in a future release once consumers migrate.
            "trace_id": trace_id,
            "request_id": request_id,
        }
        try:
            put_run(runs_table, run_record)
        except Exception as exc:  # pragma: no cover - defensive logging path
            _log_json(
                {
                    "service": SERVICE,
                    "component": COMPONENT,
                    "mode": req.mode,
                    "level": "warning",
                    "code": "run_persistence_failed",
                    "message": str(exc),
                    "run_id": run_record["run_id"],
                    "request_id": request_id,
                    "correlation_id": trace_id,
                    # DEPRECATED: trace_id retained for backward compatibility
                    "trace_id": trace_id,
                }
            )

    # Add correlation ID to response
    if trace_id:
        result["correlation_id"] = trace_id

    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(result),
    }
