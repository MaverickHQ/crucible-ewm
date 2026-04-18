"""Run evaluator CLI module."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.core.eval.run_evaluator import (
    evaluate_run,
    load_run_artifacts,
    write_evaluation,
)

# CLI-specific integrity error codes
CLI_INTEGRITY_ERROR_CODES = {
    "run_dir_missing": "run_dir_missing",
}


def run_evaluate_cmd(args: argparse.Namespace) -> int:
    """
    Evaluate a run's artifacts and print summary.

    Args:
        args: Parsed command-line arguments with:
            - artifacts_dir: Path to the artifact directory (or root if --run-id provided)
            - run_id: Optional run ID to resolve subdirectory
            - json: Whether to print full JSON output

    Returns:
        Exit code:
            0 -> integrity.manifest_valid == true AND no integrity_errors
            2 -> any integrity_errors present
            1 -> unexpected runtime exception
    """
    artifacts_dir = Path(args.artifacts_dir)
    run_id = getattr(args, "run_id", None)

    # Determine the actual run directory based on --run-id
    if run_id is not None:
        # --run-id provided: treat artifacts-dir as root, resolve subdirectory
        run_dir = artifacts_dir / run_id
    else:
        # --run-id not provided: treat artifacts-dir as the run directory directly
        run_dir = artifacts_dir

    # Validate run directory exists
    if not run_dir.exists():
        return _handle_missing_run_dir(artifacts_dir, run_id, args)

    if not run_dir.is_dir():
        print(f"Error: run directory is not a directory: {run_dir}", file=sys.stderr)
        return 1

    try:
        # Load artifacts
        artifacts = load_run_artifacts(run_dir)

        # Run evaluation
        evaluation = evaluate_run(artifacts, artifact_dir=run_dir)

        # Write evaluation.json to the run directory
        output_path = write_evaluation(run_dir, evaluation)

        # Print JSON output if --json flag is set
        if getattr(args, "json", False):
            print(json.dumps(evaluation, indent=2, sort_keys=True))

        # Print human-readable summary
        _print_summary(evaluation, output_path)

        # Determine exit code
        integrity = evaluation.get("integrity", {})
        manifest_valid = integrity.get("manifest_valid", False)
        integrity_errors = integrity.get("integrity_errors", [])

        if manifest_valid and not integrity_errors:
            return 0
        elif integrity_errors:
            return 2
        else:
            # Should not happen - but return 1 for unexpected state
            return 1

    except Exception as e:
        print(f"Error during evaluation: {e}", file=sys.stderr)
        return 1


def _handle_missing_run_dir(
    artifacts_dir: Path,
    run_id: str | None,
    args: argparse.Namespace,
) -> int:
    """
    Handle the case where the resolved run directory does not exist.

    Args:
        artifacts_dir: The artifacts directory (root or direct)
        run_id: The run ID if provided, None otherwise
        args: Parsed command-line arguments

    Returns:
        Exit code 2
    """
    error_code = CLI_INTEGRITY_ERROR_CODES["run_dir_missing"]

    if run_id is not None:
        resolved_path = artifacts_dir / run_id
        msg = f"Run directory does not exist: {resolved_path}"
    else:
        msg = f"Run directory does not exist: {artifacts_dir}"

    # Build minimal deterministic evaluation JSON for --json flag case
    evaluation = {
        "constraint": {},
        "integrity": {
            "manifest_valid": False,
            "integrity_errors": [error_code],
            "integrity_error_details": [
                {"code": error_code, "message": msg}
            ],
        },
        "run_id": run_id,
        "structure": {},
    }

    # Print JSON output if --json flag is set
    if getattr(args, "json", False):
        print(json.dumps(evaluation, indent=2, sort_keys=True))

    # Print human-readable summary
    print(f"Run ID: {run_id if run_id else 'null'}")
    print("Manifest valid: False")
    print(f"Integrity errors: {error_code}")
    print("Steps executed: null")
    print("Truncated by budget: null")
    print("Evaluation written to: (none - directory missing)")

    return 2


def _print_summary(evaluation: dict, output_path: Path) -> None:
    """Print human-readable summary of evaluation results."""
    integrity = evaluation.get("integrity", {})
    structure = evaluation.get("structure", {})
    constraint = evaluation.get("constraint", {})
    run_id = evaluation.get("run_id")

    # Run ID
    run_id_str = run_id if run_id else "null"

    # Manifest valid
    manifest_valid = integrity.get("manifest_valid", False)

    # Integrity errors
    integrity_errors = integrity.get("integrity_errors", [])
    if integrity_errors:
        errors_str = ", ".join(integrity_errors)
    else:
        errors_str = "none"

    # Steps executed
    steps_executed = structure.get("steps_executed")
    steps_str = str(steps_executed) if steps_executed is not None else "null"

    # Truncated by budget
    truncated = constraint.get("truncated_by_budget")
    truncated_str = str(truncated) if truncated is not None else "null"

    # Print summary
    print(f"Run ID: {run_id_str}")
    print(f"Manifest valid: {manifest_valid}")
    print(f"Integrity errors: {errors_str}")
    print(f"Steps executed: {steps_str}")
    print(f"Truncated by budget: {truncated_str}")
    print(f"Evaluation written to: {output_path}")


def experiment_evaluate_placeholder(args: argparse.Namespace) -> int:
    """
    Evaluate an experiment's runs and compute aggregated metrics.
    
    Supports two directory structures:
    A) artifacts/<run_id>/ - run artifacts inside artifacts/ subdirectory
    B) <run_id>/ - run artifacts directly in experiment directory

    Args:
        args: Parsed command-line arguments with:
            - experiment_dir: Path to the experiment directory
            - json: Whether to print full JSON output

    Returns:
        Exit code:
            0 -> no integrity errors at experiment level AND no run integrity errors
            2 -> any integrity errors exist OR experiment integrity failure
            1 -> unexpected runtime exception
    """
    from services.core.eval.experiment_evaluator import (
        evaluate_experiment,
        write_experiment_evaluation,
    )
    
    experiment_dir = Path(args.experiment_dir)
    
    try:
        # Evaluate experiment
        evaluation = evaluate_experiment(experiment_dir)
        
        # Write evaluation files
        json_path, csv_path = write_experiment_evaluation(experiment_dir, evaluation)
        
        # Print JSON output if --json flag is set
        if getattr(args, "json", False):
            import json
            print(json.dumps(evaluation, indent=2, sort_keys=True))
        
        # Print human-readable summary
        _print_experiment_summary(evaluation, json_path)
        
        # Determine exit code
        integrity = evaluation.get("integrity", {})
        experiment_integrity_errors = integrity.get("integrity_errors", [])
        
        # Check for any run-level integrity errors
        runs = evaluation.get("runs", [])
        any_run_errors = any(r.get("integrity_errors") for r in runs)
        
        if not experiment_integrity_errors and not any_run_errors:
            return 0
        else:
            return 2
            
    except Exception as e:
        print(f"Error during experiment evaluation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _print_experiment_summary(evaluation: dict, json_path: Path) -> None:
    """Print human-readable summary of experiment evaluation results."""
    aggregate = evaluation.get("aggregate", {})
    integrity = evaluation.get("integrity", {})

    # Total runs
    total_runs = aggregate.get("total_runs", 0)

    # Integrity failures
    runs_with_errors = aggregate.get("runs_with_integrity_errors", 0)

    # Avg steps
    avg_steps = aggregate.get("avg_steps_executed")
    avg_steps_str = f"{avg_steps:.2f}" if avg_steps is not None else "null"

    # Experiment-level integrity errors
    exp_errors = integrity.get("integrity_errors", [])
    if exp_errors:
        errors_str = ", ".join(exp_errors)
    else:
        errors_str = "none"

    # Print summary
    print(f"Total runs: {total_runs}")
    print(f"Integrity failures: {runs_with_errors}")
    print(f"Avg steps: {avg_steps_str}")
    print(f"Experiment integrity errors: {errors_str}")
    print(f"Evaluation written to: {json_path}")
