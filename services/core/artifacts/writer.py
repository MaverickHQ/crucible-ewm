from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from services.core.simulator import SimulationResult

if TYPE_CHECKING:
    from services.core.loop.types import LoopResult

# Runtime version constant - should match package version
RUNTIME_VERSION = "0.8.3"

# Runtime budget keys - these belong in runtime_budgets
RUNTIME_BUDGET_KEYS = frozenset(
    {
        "max_steps",
        "max_tool_calls",
        "max_model_calls",
        "max_memory_ops",
        "max_memory_bytes",
    }
)

# Policy/Trading limit keys - these belong in policy_limits
POLICY_LIMIT_KEYS = frozenset(
    {
        "max_leverage",
        "max_position_pct",
        "max_position_value",
    }
)


@dataclass
class RunContext:
    """
    Context object containing resolved runtime values for a run.
    This ensures manifest has the actual values used (after defaults applied).

    Manifest v2 schema:
    - runtime_budgets: runtime loop constraints (max_steps, max_tool_calls, etc.)
    - policy_limits: trading/risk constraints (max_leverage, max_position_pct, etc.)
    - budgets: deprecated alias for runtime_budgets (for backward compatibility)
    """

    run_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mode: str = "agentcore-loop"  # Default mode for local runs
    correlation_id: Optional[str] = None
    strategy_path: str = "examples/fixtures/trading_path.json"  # Default fixture
    runtime_budgets: Dict[str, object] = field(default_factory=dict)
    policy_limits: Dict[str, object] = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)
    artifact_s3_prefix: Optional[str] = None


def serialize_simulation_result(result: SimulationResult) -> Dict[str, dict]:
    """
    Serialize a SimulationResult into artifact payloads.

    Returns dictionaries ready for JSON serialization.
    Shared by both local and S3 artifact writers.
    """
    trajectory_payload = {
        "run_id": result.run_id,
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
                "price_context": step.price_context,
                "accepted": step.accepted,
                "errors": [{"code": error.code, "message": error.message} for error in step.errors],
                "explanation": step.explanation,
                "state_delta": step.state_delta,
            }
            for step in result.steps
        ],
    }

    decision_payload = {
        "run_id": result.run_id,
        "approved": result.approved,
        "rejected_step_index": result.rejected_step_index,
        "errors": [
            {
                "step_index": step.step_index,
                "errors": [{"code": error.code, "message": error.message} for error in step.errors],
            }
            for step in result.steps
            if step.errors
        ],
        "planner": {
            "planner_name": result.planner_name,
            "planner_metadata": result.planner_metadata,
        },
        "policy": {
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
            "policy_hash": result.policy_hash,
        },
    }

    deltas_payload = {
        "run_id": result.run_id,
        "deltas": [step.state_delta for step in result.steps],
    }

    return {
        "trajectory": trajectory_payload,
        "decision": decision_payload,
        "deltas": deltas_payload,
    }


def _split_budgets_dict(
    budgets: Optional[Dict[str, object]],
) -> tuple[Dict[str, object], Dict[str, object]]:
    """
    Split a budgets dict into runtime_budgets and policy_limits.

    Args:
        budgets: Raw budgets dict that may contain both runtime and policy keys

    Returns:
        Tuple of (runtime_budgets, policy_limits)
    """
    if not budgets:
        return {}, {}

    runtime_budgets = {}
    policy_limits = {}

    for key, value in budgets.items():
        if key in RUNTIME_BUDGET_KEYS:
            runtime_budgets[key] = value
        elif key in POLICY_LIMIT_KEYS:
            policy_limits[key] = value
        else:
            # Unknown keys go to runtime_budgets for backward compatibility
            runtime_budgets[key] = value

    return runtime_budgets, policy_limits


def serialize_manifest(
    result: SimulationResult,
    mode: Optional[str] = None,
    correlation_id: Optional[str] = None,
    strategy_path: Optional[str] = None,
    budgets: Optional[Dict[str, object]] = None,
    symbols: Optional[list[str]] = None,
    artifact_s3_prefix: Optional[str] = None,
    runtime_budgets: Optional[Dict[str, object]] = None,
    policy_limits: Optional[Dict[str, object]] = None,
) -> dict:
    """
    Serialize a SimulationResult into a manifest payload.

    The manifest includes metadata about the run execution for auditability,
    reproducibility, and debugging.

    Manifest v2 schema:
    - manifest_version: "2"
    - runtime_budgets: runtime loop constraints (max_steps, max_tool_calls, etc.)
    - policy_limits: trading/risk constraints (max_leverage, max_position_pct, etc.)
    - budgets: deprecated alias for runtime_budgets (for backward compatibility)

    Args:
        result: The simulation result to generate manifest from
        mode: Execution mode (e.g., "backtest", "paper", "live")
        correlation_id: Client-provided correlation ID for tracing
        strategy_path: Path to the strategy file used
        budgets: Legacy budgets dict - will be split into runtime_budgets/policy_limits
        symbols: List of symbols traded in this run
        artifact_s3_prefix: S3 prefix for uploaded artifacts
        runtime_budgets: Explicit runtime budgets (preferred)
        policy_limits: Explicit policy limits (preferred)

    Returns:
        A dictionary ready for JSON serialization with stable key ordering
    """
    # Extract symbols from the trajectory/steps if not provided
    if symbols is None:
        symbol_set = set()
        for step in result.steps:
            if hasattr(step.action, "symbol"):
                symbol_set.add(step.action.symbol)
        symbols = sorted(symbol_set) if symbol_set else []

    # Process budgets - either use explicit runtime_budgets/policy_limits or split from budgets
    if runtime_budgets is not None or policy_limits is not None:
        # Use explicit values
        final_runtime_budgets = dict(runtime_budgets) if runtime_budgets else {}
        final_policy_limits = dict(policy_limits) if policy_limits else {}
    elif budgets:
        # Split legacy budgets into runtime and policy
        final_runtime_budgets, final_policy_limits = _split_budgets_dict(budgets)
    else:
        final_runtime_budgets = {}
        final_policy_limits = {}

    # Build manifest v2 with deterministic key ordering (alphabetical)
    manifest = {
        "manifest_version": "2",
        "run_id": result.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_version": RUNTIME_VERSION,
        "mode": mode,
        "correlation_id": correlation_id,
        "strategy_path": strategy_path,
        "runtime_budgets": final_runtime_budgets,
        "policy_limits": final_policy_limits,
        "symbols": symbols,
    }

    # Backward compatibility: include deprecated "budgets" alias ONLY if runtime_budgets exists
    # This alias is for v1 compatibility - it equals runtime_budgets
    if final_runtime_budgets:
        manifest["budgets"] = final_runtime_budgets

    # Add S3 prefix if artifact upload is enabled
    if artifact_s3_prefix:
        manifest["artifact_s3_prefix"] = artifact_s3_prefix

    return manifest


def serialize_manifest_from_context(result: SimulationResult, context: RunContext) -> dict:
    """
    Serialize a manifest from a RunContext.

    This is the preferred way to generate a manifest when you have resolved values.
    Produces manifest v2 format with runtime_budgets and policy_limits separated.

    Args:
        result: The simulation result to generate manifest from
        context: RunContext with resolved runtime values

    Returns:
        A dictionary ready for JSON serialization with stable key ordering
    """
    # Extract symbols from the trajectory/steps if not provided in context
    symbols = context.symbols
    if not symbols:
        symbol_set = set()
        for step in result.steps:
            if hasattr(step.action, "symbol"):
                symbol_set.add(step.action.symbol)
        symbols = sorted(symbol_set) if symbol_set else []

    # Build manifest v2 with deterministic key ordering (alphabetical)
    manifest = {
        "manifest_version": "2",
        "run_id": context.run_id,
        "created_at": context.created_at,
        "runtime_version": RUNTIME_VERSION,
        "mode": context.mode,
        "correlation_id": context.correlation_id,
        "strategy_path": context.strategy_path,
        "runtime_budgets": context.runtime_budgets,
        "policy_limits": context.policy_limits,
        "symbols": symbols,
    }

    # Backward compatibility: include deprecated "budgets" alias ONLY if runtime_budgets exists
    # This alias is for v1 compatibility - it equals runtime_budgets
    if context.runtime_budgets:
        manifest["budgets"] = context.runtime_budgets

    # Add S3 prefix if artifact upload is enabled
    if context.artifact_s3_prefix:
        manifest["artifact_s3_prefix"] = context.artifact_s3_prefix

    return manifest


def serialize_manifest_from_loop_result(
    loop_result: "LoopResult",
    run_id: str,
    mode: str,
    strategy_path: str,
    runtime_budgets: Dict[str, object],
    policy_limits: Dict[str, object],
    correlation_id: Optional[str] = None,
    artifact_s3_prefix: Optional[str] = None,
) -> dict:
    """
    Serialize a manifest from a LoopResult (agentcore-loop execution).

    This is the canonical way to generate a manifest for agentcore-loop runs,
    used by both local artifact writing and S3 upload. Ensures schema consistency.

    Manifest v2 schema:
    - manifest_version: "2"
    - runtime_budgets: runtime loop constraints (max_steps, max_tool_calls, etc.)
    - policy_limits: trading/risk constraints (max_leverage, max_position_pct, etc.)
    - budgets: deprecated alias for runtime_budgets (for backward compatibility)

    Args:
        loop_result: The LoopResult from run_loop()
        run_id: The run identifier
        mode: Execution mode (e.g., "agentcore-loop")
        strategy_path: Path to the strategy file used
        runtime_budgets: Runtime loop constraints
        policy_limits: Trading/risk constraints
        correlation_id: Client-provided correlation ID for tracing
        artifact_s3_prefix: S3 prefix for uploaded artifacts

    Returns:
        A dictionary ready for JSON serialization with stable key ordering
    """
    # Extract symbols from tape_rows (actions contain symbols)
    symbol_set = set()
    for tape_row in loop_result.tape_rows:
        for action in tape_row.actions:
            if isinstance(action, dict) and "symbol" in action:
                symbol_set.add(action["symbol"])
            elif hasattr(action, "symbol"):
                symbol_set.add(action.symbol)
    symbols = sorted(symbol_set) if symbol_set else []

    # Build manifest v2 with deterministic key ordering (alphabetical)
    manifest = {
        "manifest_version": "2",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_version": RUNTIME_VERSION,
        "mode": mode,
        "correlation_id": correlation_id,
        "strategy_path": strategy_path,
        "runtime_budgets": runtime_budgets,
        "policy_limits": policy_limits,
        "symbols": symbols,
    }

    # Backward compatibility: include deprecated "budgets" alias ONLY if runtime_budgets exists
    # This alias is for v1 compatibility - it equals runtime_budgets
    if runtime_budgets:
        manifest["budgets"] = runtime_budgets

    # Add S3 prefix if artifact upload is enabled
    if artifact_s3_prefix:
        manifest["artifact_s3_prefix"] = artifact_s3_prefix

    return manifest


@dataclass
class ArtifactWriter:
    output_dir: Path

    def write(
        self,
        result: SimulationResult,
        context: Optional[RunContext] = None,
    ) -> Dict[str, Path]:
        run_dir = self.output_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        payloads = serialize_simulation_result(result)

        trajectory_path = run_dir / "trajectory.json"
        decision_path = run_dir / "decision.json"
        deltas_path = run_dir / "deltas.json"

        trajectory_path.write_text(json.dumps(payloads["trajectory"], indent=2))
        decision_path.write_text(json.dumps(payloads["decision"], indent=2))
        deltas_path.write_text(json.dumps(payloads["deltas"], indent=2))

        # Generate and write manifest with stable key ordering
        if context is not None:
            manifest_payload = serialize_manifest_from_context(result, context)
        else:
            manifest_payload = serialize_manifest(result)

        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True))

        return {
            "trajectory": trajectory_path,
            "decision": decision_path,
            "deltas": deltas_path,
            "manifest": manifest_path,
        }
