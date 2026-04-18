#!/usr/bin/env python3
"""Script to export validated experiment trajectories to a learning-ready dataset.

Usage:
    python3 scripts/export_learning_dataset.py --experiment-dir <path> --output <path>

This script:
1. Loads experiment evaluation results
2. Selects structurally valid runs for learning
3. Exports trajectory data to JSONL format
"""

import argparse
import sys
from pathlib import Path

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.learning import export_learning_dataset, select_learning_runs


def main():
    parser = argparse.ArgumentParser(
        description="Export validated experiment trajectories to learning dataset"
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="Path to the experiment directory containing evaluation results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the JSONL learning dataset",
    )
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Include structurally invalid runs (default: only valid runs)",
    )
    
    args = parser.parse_args()
    
    experiment_dir = args.experiment_dir
    output_path = args.output
    require_valid = not args.include_invalid
    
    # Validate experiment directory
    if not experiment_dir.exists():
        print(f"ERROR: Experiment directory does not exist: {experiment_dir}")
        sys.exit(1)
    
    eval_summary = experiment_dir / "evaluation_summary.json"
    if not eval_summary.exists():
        print(f"ERROR: evaluation_summary.json not found in {experiment_dir}")
        print("Run evaluation first using the evaluate experiment command.")
        sys.exit(1)
    
    # Select runs
    print(f"Selecting runs from: {experiment_dir}")
    selected_runs = select_learning_runs(
        experiment_dir,
        require_valid=require_valid,
        include_truncated=True,
    )
    
    print(f"  Selected {len(selected_runs)} runs for learning")
    
    # Export dataset
    print(f"Exporting dataset to: {output_path}")
    result_path = export_learning_dataset(
        experiment_dir,
        output_path,
        require_valid=require_valid,
    )
    
    # Count rows
    row_count = 0
    with open(result_path) as f:
        for line in f:
            if line.strip():
                row_count += 1
    
    print(f"  Wrote {row_count} trajectory steps")
    print(f"  Output: {result_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
