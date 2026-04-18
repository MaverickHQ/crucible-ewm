"""Selector module for choosing eligible runs for learning.

This module selects runs based on structural validity criteria. Only runs that
pass integrity checks are eligible for learning inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


def load_evaluation_runs(experiment_dir: Path) -> List[dict]:
    """
    Load run evaluations from experiment directory.
    
    Args:
        experiment_dir: Path to the experiment directory.
        
    Returns:
        List of run evaluation dictionaries from evaluation_summary.json.
        
    Raises:
        FileNotFoundError: If evaluation_summary.json doesn't exist.
    """
    experiment_dir = Path(experiment_dir)
    eval_path = experiment_dir / "evaluation_summary.json"
    
    if not eval_path.exists():
        raise FileNotFoundError(
            f"evaluation_summary.json not found in {experiment_dir}. "
            "Run evaluation first using evaluate_experiment()."
        )
    
    with open(eval_path) as f:
        evaluation = json.load(f)
    
    runs = evaluation.get("runs", [])
    
    # Sort by run_id for deterministic ordering
    runs.sort(key=lambda r: r.get("run_id", ""))
    
    return runs


def select_learning_runs(
    experiment_dir: Path,
    *,
    require_valid: bool = True,
    include_truncated: bool = True,
) -> List[dict]:
    """
    Select runs that are eligible for learning based on structural validity.
    
    Default behavior selects only runs where:
    - manifest_valid == true
    - no integrity_errors
    
    This ensures only trusted experimental evidence enters the learning loop
    (Essay 10 principle).
    
    Args:
        experiment_dir: Path to the experiment directory.
        require_valid: If True, only include runs with manifest_valid=True.
                      If False, include all runs.
        include_truncated: If True, include structurally valid runs that were
                          truncated by budget. If False, exclude truncated runs.
    
    Returns:
        List of selected run dictionaries, sorted by run_id.
        
    Raises:
        FileNotFoundError: If evaluation_summary.json doesn't exist.
    """
    runs = load_evaluation_runs(experiment_dir)
    
    selected_runs: List[dict] = []
    
    for run in runs:
        manifest_valid = run.get("manifest_valid", False)
        integrity_errors = run.get("integrity_errors", [])
        truncated = run.get("truncated_by_budget")
        
        # Skip runs with integrity errors if require_valid
        if require_valid and not manifest_valid:
            continue
        
        if require_valid and integrity_errors:
            continue
        
        # Skip truncated runs if not included
        if not include_truncated and truncated is True:
            continue
        
        selected_runs.append(run)
    
    # Ensure deterministic ordering by run_id
    selected_runs.sort(key=lambda r: r.get("run_id", ""))
    
    return selected_runs
