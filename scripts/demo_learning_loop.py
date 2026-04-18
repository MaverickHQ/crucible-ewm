#!/usr/bin/env python3
"""Demo script demonstrating the full learning loop scaffold.

This script demonstrates the complete learning loop using the trading example:
1. Uses existing experiment data (or creates fixture data if needed)
2. Exports learning dataset
3. Runs stub learner
4. Shows readable output

Usage:
    python3 scripts/demo_learning_loop.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.learning import (
    export_learning_dataset,
    run_stub_learner,
    select_learning_runs,
)


def create_demo_experiment(tmp_dir: Path) -> Path:
    """Create a minimal demo experiment directory with fixture data."""
    experiment_dir = tmp_dir / "demo_learning_experiment"
    artifacts_dir = experiment_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    
    # Create evaluation_summary.json
    evaluation = {
        "aggregate": {
            "total_runs": 3,
            "runs_with_integrity_errors": 0,
            "runs_without_integrity_errors": 3,
            "pct_integrity_fail": 0.0,
            "avg_steps_executed": 5.0,
            "pct_truncated_by_budget": 33.33,
            "max_steps_executed": 10,
            "min_steps_executed": 2,
        },
        "integrity": {
            "experiment_dir_exists": True,
            "results_jsonl_present": True,
            "artifact_dirs_found": 3,
            "integrity_errors": [],
        },
        "runs": [
            {
                "run_id": "run-001",
                "manifest_valid": True,
                "integrity_errors": [],
                "steps_executed": 10,
                "truncated_by_budget": True,
            },
            {
                "run_id": "run-002",
                "manifest_valid": True,
                "integrity_errors": [],
                "steps_executed": 5,
                "truncated_by_budget": False,
            },
            {
                "run_id": "run-003",
                "manifest_valid": True,
                "integrity_errors": [],
                "steps_executed": 2,
                "truncated_by_budget": False,
            },
        ],
        "summary": {
            "total_runs": 3,
            "ok_runs": 3,
            "failed_runs": 0,
        },
    }
    
    (experiment_dir / "evaluation_summary.json").write_text(
        json.dumps(evaluation, indent=2)
    )
    
    # Create run artifacts
    for run_id, steps in [("run-001", 10), ("run-002", 5), ("run-003", 2)]:
        run_dir = artifacts_dir / run_id
        run_dir.mkdir()
        
        # Create manifest
        manifest = {
            "manifest_version": "2",
            "run_id": run_id,
            "mode": "trading",
            "symbols": ["AAPL", "MSFT"],
            "runtime_version": "0.8.4",
            "strategy_path": "examples/strategies/threshold_demo.json",
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        
        # Create trajectory
        trajectory = []
        actions = ["hold", "buy", "sell"]
        for i in range(steps):
            step = {
                "observation": {"step": i, "prices": {"AAPL": 100 + i, "MSFT": 200 + i}},
                "action": {"type": actions[i % 3], "symbol": "AAPL" if i % 2 == 0 else "MSFT"},
                "next_observation": {"step": i + 1, "prices": {"AAPL": 101 + i, "MSFT": 201 + i}},
                "done": i == steps - 1,
            }
            trajectory.append(step)
        (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        
        # Create other required artifacts (empty/dummy)
        (run_dir / "decision.json").write_text(json.dumps({"run_id": run_id}))
        (run_dir / "deltas.json").write_text(json.dumps({"run_id": run_id, "deltas": []}))
    
    return experiment_dir


def main():
    print("=" * 60)
    print("LEARNING LOOP SCAFFOLD DEMO")
    print("=" * 60)
    print()
    
    # Use the fixture experiment for demo (contains real trajectory data)
    fixture_experiment = Path("tests/fixtures/learning_experiment")
    if fixture_experiment.exists() and (fixture_experiment / "evaluation_summary.json").exists():
        experiment_dir = fixture_experiment
        print(f"Using fixture experiment: {experiment_dir}")
    else:
        print("Creating demo experiment fixtures...")
        tmp_dir = Path(tempfile.mkdtemp())
        experiment_dir = create_demo_experiment(tmp_dir)
        print(f"Created demo experiment: {experiment_dir}")
    
    print()
    print("-" * 60)
    print("STEP 1: Select Learning Runs")
    print("-" * 60)
    
    selected_runs = select_learning_runs(
        experiment_dir,
        require_valid=True,
        include_truncated=True,
    )
    
    print(f"  Experiment: {experiment_dir}")
    print(f"  Selected {len(selected_runs)} runs")
    for run in selected_runs[:5]:  # Show first 5
        print(f"    - {run['run_id']}: {run['steps_executed']} steps, truncated={run.get('truncated_by_budget')}")
    if len(selected_runs) > 5:
        print(f"    ... and {len(selected_runs) - 5} more")
    
    print()
    print("-" * 60)
    print("STEP 2: Export Learning Dataset")
    print("-" * 60)
    
    # Create output path
    output_dir = Path("outputs/learning")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    dataset_path = output_dir / "demo_trajectories.jsonl"
    
    result_path = export_learning_dataset(
        experiment_dir,
        dataset_path,
        require_valid=True,
    )
    
    # Count rows
    row_count = 0
    with open(result_path) as f:
        for line in f:
            if line.strip():
                row_count += 1
    
    print(f"  Dataset: {result_path}")
    print(f"  Rows exported: {row_count}")
    
    print()
    print("-" * 60)
    print("STEP 3: Run Stub Learner")
    print("-" * 60)
    
    report_path = output_dir / "demo_learning_report.json"
    
    run_stub_learner(result_path, report_path)
    
    # Show report summary
    with open(report_path) as f:
        report = json.load(f)
    
    print(f"  Report: {report_path}")
    print(f"  Total runs: {report['total_runs']}")
    print(f"  Total steps: {report['total_steps']}")
    print(f"  Avg steps/run: {report['average_steps_per_run']}")
    print(f"  Action counts: {report['action_counts']}")
    print(f"  Symbol counts: {report['symbol_counts']}")
    
    print()
    print("-" * 60)
    print("LEARNING LOOP COMPLETE")
    print("-" * 60)
    print()
    print("This demonstrates the v0.8.4 learning scaffold:")
    print("  1. Selects structurally valid runs")
    print("  2. Exports trajectory data to JSONL")
    print("  3. Computes aggregate statistics")
    print()
    print("This is NOT RL training - it's a deterministic scaffold")
    print("that proves the architecture can close the loop from")
    print("experiments to learning inputs (Essay 10).")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
