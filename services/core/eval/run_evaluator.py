"""Run evaluator module for computing structural, constraint, and integrity metrics."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# Required artifact files
REQUIRED_ARTIFACT_FILES = [
    "manifest.json",
    "decision.json",
    "trajectory.json",
    "deltas.json",
]

# Expected manifest version
MANIFEST_VERSION_EXPECTED = "2"

# Integrity error codes (stable, deterministic, machine-readable)
INTEGRITY_ERROR_CODES = {
    "manifest_missing": "manifest_missing",
    "manifest_invalid_json": "manifest_invalid_json",
    "manifest_version_mismatch": "manifest_version_mismatch",
    "required_files_missing": "required_files_missing",
    "run_id_mismatch": "run_id_mismatch",
}


def load_run_artifacts(artifact_dir: Path) -> dict:
    """
    Load all artifact files from a run's artifact directory.
    
    Args:
        artifact_dir: Path to the directory containing run artifacts.
        
    Returns:
        Dictionary with keys 'manifest', 'decision', 'trajectory', 'deltas'.
        Each value is the parsed JSON content. If a required file is missing,
        it will not be present in the returned dictionary.
        
    Raises:
        json.JSONDecodeError: If any artifact file contains invalid JSON.
    """
    artifacts: Dict[str, Any] = {}
    parse_errors: list[str] = []
    
    for filename in REQUIRED_ARTIFACT_FILES:
        file_path = artifact_dir / filename
        if not file_path.exists():
            # File is missing - skip it, evaluation will handle required_files_present
            continue
        
        try:
            with open(file_path) as f:
                artifacts[filename.replace(".json", "")] = json.load(f)
        except json.JSONDecodeError as e:
            parse_errors.append(f"{filename}: {str(e)}")
            raise
    
    return artifacts


def _check_uuid_format(dir_name: str) -> bool:
    """Check if a directory name looks like a UUID."""
    try:
        uuid.UUID(dir_name)
        return True
    except (ValueError, AttributeError):
        return False


def _compute_steps_executed(trajectory: Any) -> Optional[int]:
    """
    Compute steps_executed from trajectory artifact.
    
    Handles multiple schema variants:
    - List: steps_executed = len(list)
    - Dict with "tape" key: steps_executed = len(tape)
    - Unknown: return None
    
    Args:
        trajectory: Parsed trajectory JSON (can be list or dict)
        
    Returns:
        Number of steps executed, or None if schema is unknown.
    """
    if isinstance(trajectory, list):
        return len(trajectory)
    
    if isinstance(trajectory, dict):
        if "tape" in trajectory and isinstance(trajectory["tape"], list):
            return len(trajectory["tape"])
        # Has trajectory key which is a list
        if "trajectory" in trajectory and isinstance(trajectory["trajectory"], list):
            return len(trajectory["trajectory"])
    
    # Unknown schema
    return None


def evaluate_run(
    artifacts: dict,
    *,
    artifact_dir: Optional[Path] = None,
) -> dict:
    """
    Evaluate a run's artifacts and compute structural, constraint, and integrity metrics.
    
    Args:
        artifacts: Dictionary with keys 'manifest', 'decision', 'trajectory', 'deltas'.
        artifact_dir: Optional path to artifact directory (for run_id consistency check).
        
    Returns:
        Evaluation dictionary with integrity, structure, and constraint metrics.
    """
    # Use stable error codes instead of human strings
    integrity_error_codes: list[str] = []
    # Detailed error messages for humans (deterministic, no timestamps/random IDs)
    integrity_error_details: list[dict] = []
    parse_errors: list[str] = []
    integrity_warnings: list[str] = []
    
    # =============================================================================
    # INTEGRITY METRICS
    # =============================================================================
    manifest_version: Optional[str] = None
    manifest_valid: bool = True
    
    # Check manifest
    manifest = artifacts.get("manifest")
    if manifest is None:
        manifest_valid = False
        integrity_error_codes.append(INTEGRITY_ERROR_CODES["manifest_missing"])
        integrity_error_details.append({
            "code": INTEGRITY_ERROR_CODES["manifest_missing"],
            "message": "manifest.json not found",
        })
    else:
        # Check manifest_version
        manifest_version = manifest.get("manifest_version")
        if manifest_version != MANIFEST_VERSION_EXPECTED:
            manifest_valid = False
            code = INTEGRITY_ERROR_CODES["manifest_version_mismatch"]
            integrity_error_codes.append(code)
            msg = (
                f"manifest_version is '{manifest_version}', "
                f"expected '{MANIFEST_VERSION_EXPECTED}'"
            )
            integrity_error_details.append({
                "code": code,
                "message": msg,
            })
    
    # Check required files present
    required_files_present = all(
        filename.replace(".json", "") in artifacts
        for filename in REQUIRED_ARTIFACT_FILES
    )
    
    # Check run_id consistency
    run_id_consistent = True
    run_id: Optional[str] = None
    
    if manifest:
        run_id = manifest.get("run_id")
        
        if artifact_dir and run_id:
            # Check if artifact_dir name looks like a UUID and matches manifest.run_id
            dir_name = artifact_dir.name
            if _check_uuid_format(dir_name):
                if dir_name != run_id:
                    run_id_consistent = False
                    code = INTEGRITY_ERROR_CODES["run_id_mismatch"]
                    integrity_error_codes.append(code)
                    msg = (
                        f"artifact_dir name '{dir_name}' does not match "
                        f"manifest.run_id '{run_id}'"
                    )
                    integrity_error_details.append({
                        "code": code,
                        "message": msg,
                    })
        
        # Check run_id consistency across all artifacts
        for filename in ["decision", "trajectory", "deltas"]:
            artifact = artifacts.get(filename)
            if artifact and isinstance(artifact, dict):
                artifact_run_id = artifact.get("run_id")
                if artifact_run_id and artifact_run_id != run_id:
                    run_id_consistent = False
                    code = INTEGRITY_ERROR_CODES["run_id_mismatch"]
                    integrity_error_codes.append(code)
                    msg = f"{filename}.run_id '{artifact_run_id}' != manifest.run_id '{run_id}'"
                    integrity_error_details.append({
                        "code": code,
                        "message": msg,
                    })
    
    # Check for parse errors (already captured in load_run_artifacts)
    # Add any integrity issues
    if not required_files_present:
        code = INTEGRITY_ERROR_CODES["required_files_missing"]
        integrity_error_codes.append(code)
        integrity_error_details.append({
            "code": code,
            "message": "One or more required artifact files are missing",
        })
    
    if not manifest_valid:
        # Already added specific error codes above, this is a fallback
        if not integrity_error_codes:
            code = INTEGRITY_ERROR_CODES["manifest_missing"]
            integrity_error_codes.append(code)
            integrity_error_details.append({
                "code": code,
                "message": "Manifest is invalid (wrong version or missing)",
            })
    
    # Build integrity result
    integrity_result = {
        "manifest_version": manifest_version,
        "manifest_valid": manifest_valid,
        "required_files_present": required_files_present,
        "run_id_consistent": run_id_consistent,
        "parse_errors": parse_errors,
        "integrity_errors": integrity_error_codes,
        "integrity_error_details": integrity_error_details,
    }
    
    # =============================================================================
    # STRUCTURE METRICS
    # =============================================================================
    steps_executed: Optional[int] = None
    trajectory = artifacts.get("trajectory")
    
    if trajectory is not None:
        steps_executed = _compute_steps_executed(trajectory)
        if steps_executed is None:
            integrity_warnings.append(
                "trajectory schema unknown: could not compute steps_executed"
            )
    
    # Extract symbols from manifest
    symbols: list[str] = []
    if manifest and isinstance(manifest, dict):
        symbols = manifest.get("symbols", [])
    
    # Extract metadata from manifest
    mode: Optional[str] = None
    runtime_version: Optional[str] = None
    created_at: Optional[str] = None
    correlation_id: Optional[str] = None
    strategy_path: Optional[str] = None
    
    if manifest and isinstance(manifest, dict):
        mode = manifest.get("mode")
        runtime_version = manifest.get("runtime_version")
        created_at = manifest.get("created_at")
        correlation_id = manifest.get("correlation_id")
        strategy_path = manifest.get("strategy_path")
    
    # Build structure result
    structure_result = {
        "steps_executed": steps_executed,
        "symbols": symbols,
        "mode": mode,
        "runtime_version": runtime_version,
        "created_at": created_at,
        "correlation_id": correlation_id,
        "strategy_path": strategy_path,
    }
    
    # =============================================================================
    # CONSTRAINT METRICS (runtime budgets only)
    # =============================================================================
    runtime_budgets: Dict[str, Any] = {}
    policy_limits: Dict[str, Any] = {}
    runtime_budget_max_steps: Optional[int] = None
    
    if manifest and isinstance(manifest, dict):
        runtime_budgets = manifest.get("runtime_budgets", {})
        policy_limits = manifest.get("policy_limits", {})
        
        # Extract max_steps from runtime_budgets
        if isinstance(runtime_budgets, dict):
            runtime_budget_max_steps = runtime_budgets.get("max_steps")
    
    # Determine truncated_by_budget
    # True if execution stopped exactly at max_steps (structural truncation)
    # If steps_executed < max_steps, it likely ended naturally (not truncated)
    truncated_by_budget: Optional[bool] = None
    
    if (
        runtime_budget_max_steps is not None
        and steps_executed is not None
        and steps_executed == runtime_budget_max_steps
    ):
        truncated_by_budget = True
    elif runtime_budget_max_steps is not None and steps_executed is not None:
        # steps_executed < runtime_budget_max_steps means not truncated (ended naturally)
        truncated_by_budget = False
    
    # Build constraint result
    # NOTE: runtime_budget_max_steps is deprecated, use runtime_budgets_max_steps
    constraint_result = {
        "runtime_budgets": runtime_budgets,
        "policy_limits": policy_limits,
        "runtime_budgets_max_steps": runtime_budget_max_steps,  # Canonical key
        "runtime_budget_max_steps": runtime_budget_max_steps,   # Deprecated, for backward compat
        "truncated_by_budget": truncated_by_budget,
    }
    
    # =============================================================================
    # FINAL EVALUATION
    # =============================================================================
    # Build with deterministic key order: constraint, integrity, run_id, structure
    evaluation = {
        "constraint": constraint_result,
        "integrity": integrity_result,
        "run_id": run_id,
        "structure": structure_result,
    }
    
    # Add warnings if any
    if integrity_warnings:
        evaluation["integrity_warnings"] = integrity_warnings
    
    return evaluation


def write_evaluation(artifact_dir: Path, evaluation: dict) -> Path:
    """
    Write evaluation results to evaluation.json in the artifact directory.
    
    Args:
        artifact_dir: Path to the artifact directory.
        evaluation: Evaluation dictionary to write.
        
    Returns:
        Path to the written evaluation.json file.
    """
    output_path = artifact_dir / "evaluation.json"
    
    # Write with deterministic JSON formatting (sorted keys, indent 2, newline at EOF)
    output_content = json.dumps(evaluation, indent=2, sort_keys=True)
    
    # Ensure newline at EOF
    if not output_content.endswith("\n"):
        output_content += "\n"
    
    output_path.write_text(output_content)
    
    return output_path
