"""Experiment evaluator module for computing structural aggregation over multiple run artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from .run_evaluator import evaluate_run, load_run_artifacts

# Integrity error codes for experiment-level errors
EXPERIMENT_INTEGRITY_ERROR_CODES = {
    "results_jsonl_missing": "results_jsonl_missing",
    "experiment_dir_missing": "experiment_dir_missing",
}

# Required artifact files for a valid run
REQUIRED_ARTIFACT_FILES = [
    "manifest.json",
    "decision.json",
    "trajectory.json",
    "deltas.json",
]


def load_experiment_runs(experiment_dir: Path) -> List[Path]:
    """
    Load all run directories from an experiment directory.
    
    Supports two directory structures:
    A) artifacts/<run_id>/ - run artifacts inside artifacts/ subdirectory
    B) <run_id>/ - run artifacts directly in experiment directory
    
    Args:
        experiment_dir: Path to the experiment directory.
        
    Returns:
        List of paths to run artifact directories, sorted by run_id.
        
    Raises:
        FileNotFoundError: If experiment directory doesn't exist.
    """
    experiment_dir = Path(experiment_dir)
    
    if not experiment_dir.exists():
        raise FileNotFoundError(f"Experiment directory does not exist: {experiment_dir}")
    
    # Check for artifacts/ subdirectory (structure A)
    artifacts_dir = experiment_dir / "artifacts"
    
    if artifacts_dir.exists() and artifacts_dir.is_dir():
        # Structure A: artifacts/<run_id>/
        run_dirs = []
        for item in artifacts_dir.iterdir():
            if item.is_dir():
                # Check if it looks like a run directory (has at least one artifact file)
                has_artifact = any((item / f).exists() for f in REQUIRED_ARTIFACT_FILES)
                if has_artifact:
                    run_dirs.append(item)
        
        # Sort by run_id (directory name)
        run_dirs.sort(key=lambda p: p.name)
        return run_dirs
    else:
        # Structure B: experiment_dir contains run directories directly
        run_dirs = []
        for item in experiment_dir.iterdir():
            if item.is_dir():
                # Check if it looks like a run directory
                has_artifact = any((item / f).exists() for f in REQUIRED_ARTIFACT_FILES)
                if has_artifact:
                    run_dirs.append(item)
        
        # Sort by run_id (directory name)
        run_dirs.sort(key=lambda p: p.name)
        return run_dirs


def evaluate_experiment(experiment_dir: Path) -> dict:
    """
    Evaluate all runs in an experiment and compute aggregated metrics.
    
    Args:
        experiment_dir: Path to the experiment directory.
        
    Returns:
        Evaluation dictionary with aggregate, integrity, runs, and summary keys.
    """
    experiment_dir = Path(experiment_dir)
    
    # =============================================================================
    # EXPERIMENT-LEVEL INTEGRITY CHECKS
    # =============================================================================
    integrity_errors: list[str] = []
    
    # Check experiment directory exists
    experiment_dir_exists = experiment_dir.exists()
    if not experiment_dir_exists:
        integrity_errors.append(EXPERIMENT_INTEGRITY_ERROR_CODES["experiment_dir_missing"])
    
    # Check for results.jsonl
    results_jsonl_present = (experiment_dir / "results.jsonl").exists()
    if not results_jsonl_present:
        integrity_errors.append(EXPERIMENT_INTEGRITY_ERROR_CODES["results_jsonl_missing"])
    
    # Find run directories
    run_dirs: List[Path] = []
    artifact_dirs_found = 0
    
    if experiment_dir_exists:
        try:
            run_dirs = load_experiment_runs(experiment_dir)
            artifact_dirs_found = len(run_dirs)
        except FileNotFoundError:
            pass
    
    # =============================================================================
    # EVALUATE EACH RUN
    # =============================================================================
    runs_evaluation: List[dict] = []
    
    for run_dir in run_dirs:
        run_id = run_dir.name
        
        try:
            # Load artifacts for this run
            artifacts = load_run_artifacts(run_dir)
            
            # Evaluate the run using R21 evaluate_run
            evaluation = evaluate_run(artifacts, artifact_dir=run_dir)
            
            # Extract relevant fields for aggregation
            integrity = evaluation.get("integrity", {})
            structure = evaluation.get("structure", {})
            constraint = evaluation.get("constraint", {})
            
            run_result = {
                "run_id": run_id,
                "manifest_valid": integrity.get("manifest_valid", False),
                "integrity_errors": integrity.get("integrity_errors", []),
                "steps_executed": structure.get("steps_executed"),
                "truncated_by_budget": constraint.get("truncated_by_budget"),
            }
            
        except Exception as e:
            # Handle unexpected errors during run evaluation
            run_result = {
                "run_id": run_id,
                "manifest_valid": False,
                "integrity_errors": [f"evaluation_error: {str(e)}"],
                "steps_executed": None,
                "truncated_by_budget": None,
            }
        
        runs_evaluation.append(run_result)
    
    # =============================================================================
    # AGGREGATE METRICS
    # =============================================================================
    total_runs = len(runs_evaluation)
    
    runs_with_integrity_errors = sum(
        1 for r in runs_evaluation if r["integrity_errors"]
    )
    runs_without_integrity_errors = total_runs - runs_with_integrity_errors
    
    # Calculate percentage of integrity failures
    pct_integrity_fail = (
        (runs_with_integrity_errors / total_runs * 100) if total_runs > 0 else 0.0
    )
    
    # Calculate steps_executed statistics (exclude nulls)
    steps_executed_values = [
        r["steps_executed"] for r in runs_evaluation if r["steps_executed"] is not None
    ]
    
    if steps_executed_values:
        avg_steps_executed = sum(steps_executed_values) / len(steps_executed_values)
        max_steps_executed = max(steps_executed_values)
        min_steps_executed = min(steps_executed_values)
    else:
        avg_steps_executed = None
        max_steps_executed = None
        min_steps_executed = None
    
    # Calculate percentage of runs truncated by budget (exclude nulls)
    truncated_values = [
        r["truncated_by_budget"] for r in runs_evaluation 
        if r["truncated_by_budget"] is not None
    ]
    
    if truncated_values:
        pct_truncated_by_budget = (sum(truncated_values) / len(truncated_values) * 100)
    else:
        pct_truncated_by_budget = None
    
    # Build aggregate result
    aggregate = {
        "total_runs": total_runs,
        "runs_with_integrity_errors": runs_with_integrity_errors,
        "runs_without_integrity_errors": runs_without_integrity_errors,
        "pct_integrity_fail": round(pct_integrity_fail, 2),
        "avg_steps_executed": (
            round(avg_steps_executed, 2) if avg_steps_executed is not None else None
        ),
        "pct_truncated_by_budget": (
            round(pct_truncated_by_budget, 2) if pct_truncated_by_budget is not None else None
        ),
        "max_steps_executed": max_steps_executed,
        "min_steps_executed": min_steps_executed,
    }
    
    # Build integrity result
    integrity_result = {
        "experiment_dir_exists": experiment_dir_exists,
        "results_jsonl_present": results_jsonl_present,
        "artifact_dirs_found": artifact_dirs_found,
        "integrity_errors": integrity_errors,
    }
    
    # Build summary result
    summary = {
        "total_runs": total_runs,
        "ok_runs": runs_without_integrity_errors,
        "failed_runs": runs_with_integrity_errors,
    }
    
    # Build final evaluation
    evaluation = {
        "aggregate": aggregate,
        "integrity": integrity_result,
        "runs": runs_evaluation,
        "summary": summary,
    }
    
    return evaluation


def write_experiment_evaluation(experiment_dir: Path, evaluation: dict) -> tuple[Path, Path]:
    """
    Write experiment evaluation results to JSON and CSV files.
    
    Args:
        experiment_dir: Path to the experiment directory.
        evaluation: Evaluation dictionary to write.
        
    Returns:
        Tuple of (json_path, csv_path) - paths to the written files.
    """
    experiment_dir = Path(experiment_dir)
    
    # Write JSON
    json_path = experiment_dir / "evaluation_summary.json"
    json_content = json.dumps(evaluation, indent=2, sort_keys=True)
    if not json_content.endswith("\n"):
        json_content += "\n"
    json_path.write_text(json_content)
    
    # Write CSV
    csv_path = experiment_dir / "evaluation_summary.csv"
    
    runs = evaluation.get("runs", [])
    
    # Define column order (stable)
    fieldnames = [
        "run_id",
        "manifest_valid",
        "integrity_errors",
        "steps_executed",
        "truncated_by_budget",
    ]
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for run in runs:
            # Convert integrity_errors list to string representation
            integrity_errors = run.get("integrity_errors", [])
            if isinstance(integrity_errors, list):
                integrity_errors_str = ";".join(integrity_errors) if integrity_errors else ""
            else:
                integrity_errors_str = str(integrity_errors)
            
            writer.writerow({
                "run_id": run.get("run_id", ""),
                "manifest_valid": run.get("manifest_valid", False),
                "integrity_errors": integrity_errors_str,
                "steps_executed": run.get("steps_executed", ""),
                "truncated_by_budget": run.get("truncated_by_budget", ""),
            })
    
    return json_path, csv_path
