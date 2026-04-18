#!/usr/bin/env python3
"""Script to run the stub learner on a trajectory dataset.

Usage:
    python3 scripts/run_learning_stub.py --dataset <path> --output <path>

This script:
1. Loads the exported JSONL trajectory dataset
2. Computes aggregate statistics
3. Writes a learning report JSON
"""

import argparse
import json
import sys
from pathlib import Path

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.learning import run_stub_learner


def main():
    parser = argparse.ArgumentParser(
        description="Run stub learner on trajectory dataset"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to the JSONL trajectory dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the learning report JSON",
    )
    
    args = parser.parse_args()
    
    dataset_path = args.dataset
    output_path = args.output
    
    # Validate dataset path
    if not dataset_path.exists():
        print(f"ERROR: Dataset file does not exist: {dataset_path}")
        sys.exit(1)
    
    # Count rows and runs
    row_count = 0
    run_ids = set()
    
    with open(dataset_path) as f:
        for line in f:
            if line.strip():
                row_count += 1
                try:
                    data = json.loads(line)
                    run_id = data.get("run_id", "")
                    if run_id:
                        run_ids.add(run_id)
                except json.JSONDecodeError:
                    pass
    
    print(f"Loading dataset: {dataset_path}")
    print(f"  Rows: {row_count}")
    print(f"  Runs: {len(run_ids)}")
    
    # Run stub learner
    print(f"Running stub learner...")
    result_path = run_stub_learner(dataset_path, output_path)
    
    print(f"  Report: {result_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
