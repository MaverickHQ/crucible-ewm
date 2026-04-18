from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from ewm_core.agentcore_loop.types import DEFAULT_STRATEGY_PATH, LoopRequest
from ewm_core.artifacts import serialize_manifest_from_loop_result
from ewm_core.loop import run_loop
from ewm_core.market.generator import generate_market_path
from ewm_core.planner import LocalPlanner
from ewm_core.strategy import load_strategy


def _get_max_model_calls(req: LoopRequest) -> int:
    """
    Budgets can be a typed dataclass (LoopBudgets) in unit tests,
    or a dict in live JSON->pydantic/dataclass decoding. Support both.
    """
    budgets = req.budgets
    if isinstance(budgets, dict):
        return int(budgets.get("max_model_calls", 0))
    return int(getattr(budgets, "max_model_calls", 0))


def _validate_budgets(req: LoopRequest) -> None:
    if _get_max_model_calls(req) != 0:
        raise ValueError("max_model_calls must be 0 for loop-no-llm")


def _planner_enabled() -> bool:
    return os.environ.get("ENABLE_LOCAL_PLANNER", "0") == "1"


def _budget_dict(req: LoopRequest) -> dict[str, int]:
    budgets = req.budgets
    if isinstance(budgets, dict):
        return {
            "max_steps": int(budgets.get("max_steps", 5)),
            "max_tool_calls": int(budgets.get("max_tool_calls", 10)),
            "max_model_calls": int(budgets.get("max_model_calls", 0)),
            "max_memory_ops": int(budgets.get("max_memory_ops", 0)),
            "max_memory_bytes": int(budgets.get("max_memory_bytes", 0)),
        }
    return {
        "max_steps": int(getattr(budgets, "max_steps", 5)),
        "max_tool_calls": int(getattr(budgets, "max_tool_calls", 10)),
        "max_model_calls": int(getattr(budgets, "max_model_calls", 0)),
        "max_memory_ops": int(getattr(budgets, "max_memory_ops", 0)),
        "max_memory_bytes": int(getattr(budgets, "max_memory_bytes", 0)),
    }


def run_agentcore_loop(req: LoopRequest) -> Dict[str, Any]:
    # Use provided run_id if available, otherwise generate one
    # This ensures consistency across API response, S3 artifacts, and local artifacts
    run_id = req.run_id if req.run_id else str(uuid4())

    if req.mode != "agentcore-loop":
        return {
            "ok": False,
            "run_id": run_id,
            "mode": req.mode,
            "plan": None,
            "error": {"code": "invalid_mode", "message": "mode must be 'agentcore-loop'"},
        }

    try:
        _validate_budgets(req)
    except ValueError as e:
        return {
            "ok": False,
            "run_id": run_id,
            "mode": req.mode,
            "plan": None,
            "error": {"code": "invalid_budget", "message": str(e)},
        }

    market_path = generate_market_path(
        tickers=list(req.symbols),
        n_steps=req.steps,
        seed=req.seed,
    )

    strategy_path = req.strategy_path if req.strategy_path else DEFAULT_STRATEGY_PATH
    strategy = load_strategy(strategy_path)
    
    # Resolve runtime_budgets.max_steps for enforcement
    # Support both legacy budgets.max_steps and new runtime_budgets.max_steps
    runtime_budgets = _budget_dict(req)
    effective_max_steps = runtime_budgets.get("max_steps", req.steps)
    
    # Enforce max_steps budget: steps must be bounded by runtime_budgets.max_steps
    # when provided, in addition to market path length
    steps = min(req.steps, effective_max_steps, len(market_path.steps))

    planner = LocalPlanner(enabled=_planner_enabled())
    plan = planner.make_plan(
        symbols=list(req.symbols),
        steps=req.steps,
        seed=req.seed,
        write_artifacts=req.write_artifacts,
        budgets=_budget_dict(req),
    )

    data_dir = Path(tempfile.mkdtemp(prefix="agentcore-loop-"))

    result = run_loop(
        market_path=market_path,
        strategy=strategy,
        steps=steps,
        data_dir=data_dir,
        run_id=run_id,
    )

    out: Dict[str, Any] = {
        "ok": True,
        "mode": req.mode,
        "run_id": run_id,
        "plan": LocalPlanner.to_dict(plan) if plan else None,
        "steps": steps,
        "tape_length": len(result.tape_rows),
        "execution_count": len(result.execution_rows),
        "final_state": {
            "cash_balance": round(result.final_state.cash_balance, 2),
            "positions": result.final_state.positions,
        },
    }

    if req.write_artifacts:
        out["artifact_dir"] = str(data_dir)

    # Upload artifacts to S3 if enabled
    if req.upload_s3:
        artifact_bucket = os.environ.get("ARTIFACT_BUCKET", "")
        if artifact_bucket:
            try:
                import boto3

                s3_client = boto3.client("s3")
                prefix = f"artifacts/{run_id}"

                # Build trajectory payload from tape_rows
                trajectory_data = {
                    "run_id": run_id,
                    "trajectory": [state.to_dict() for state in result.tape_rows],
                }

                # Build decision payload
                decision_data = {
                    "run_id": run_id,
                    "approved": True,
                    "rejected_step_index": None,
                }

                # Build deltas payload from execution_rows
                deltas_data = {
                    "run_id": run_id,
                    "deltas": [row.to_dict() for row in result.execution_rows],
                }

                # Upload to S3
                s3_client.put_object(
                    Bucket=artifact_bucket,
                    Key=f"{prefix}/trajectory.json",
                    Body=json.dumps(trajectory_data).encode("utf-8"),
                )
                s3_client.put_object(
                    Bucket=artifact_bucket,
                    Key=f"{prefix}/decision.json",
                    Body=json.dumps(decision_data).encode("utf-8"),
                )
                s3_client.put_object(
                    Bucket=artifact_bucket,
                    Key=f"{prefix}/deltas.json",
                    Body=json.dumps(deltas_data).encode("utf-8"),
                )

                # Build and upload manifest payload using canonical serializer.
                # This ensures schema consistency between local and S3 artifacts.
                runtime_budgets = _budget_dict(req)
                # Policy limits from request (if provided), otherwise empty
                policy_limits = {}
                
                manifest_data = serialize_manifest_from_loop_result(
                    loop_result=result,
                    run_id=run_id,
                    mode=req.mode,
                    strategy_path=strategy_path,
                    runtime_budgets=runtime_budgets,
                    policy_limits=policy_limits,
                    correlation_id=None,  # Could be extended to accept from req
                    artifact_s3_prefix=f"s3://{artifact_bucket}/{prefix}",
                )
                s3_client.put_object(
                    Bucket=artifact_bucket,
                    Key=f"{prefix}/manifest.json",
                    Body=json.dumps(manifest_data, indent=2, sort_keys=True).encode("utf-8"),
                )

                out["artifact_s3_prefix"] = prefix
            except Exception as e:
                # Log error but don't fail the request
                out["artifact_s3_error"] = str(e)

    return out
