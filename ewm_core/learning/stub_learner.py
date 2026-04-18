"""Stub learner module for computing aggregate statistics from trajectory datasets.

This is NOT RL training - it's a deterministic baseline that consumes trajectory data
and produces a learning artifact/report. It computes simple, meaningful aggregate
statistics for the trading example.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict


def compute_learning_report(dataset: list[dict]) -> Dict[str, Any]:
    """
    Compute aggregate statistics from a trajectory dataset.
    
    This stub learner computes simple, meaningful statistics for the trading example:
    - total_runs, total_steps
    - action counts by type
    - symbol counts
    - proportion of hold/observe/buy/sell actions
    - dataset integrity summary
    
    Args:
        dataset: List of trajectory step dictionaries.
        
    Returns:
        Dictionary containing aggregate statistics and learning report.
    """
    if not dataset:
        return {
            "total_runs": 0,
            "total_steps": 0,
            "average_steps_per_run": 0.0,
            "action_counts": {},
            "action_proportions": {},
            "symbol_counts": {},
            "integrity_summary": {
                "valid_rows": 0,
                "invalid_rows": 0,
            },
            "heuristics": {},
        }
    
    # Track unique runs
    run_ids: set[str] = set()
    step_counts_by_run: Dict[str, int] = {}
    
    # Action and symbol counters
    action_counter: Counter = Counter()
    symbol_counter: Counter = Counter()
    
    # Track manifest validity
    valid_rows = 0
    invalid_rows = 0
    
    for step in dataset:
        run_id = step.get("run_id", "")
        if run_id:
            run_ids.add(run_id)
            step_counts_by_run[run_id] = step_counts_by_run.get(run_id, 0) + 1
        
        # Extract action
        action = step.get("action", {})
        if isinstance(action, dict):
            action_type = action.get("type", "unknown")
        else:
            action_type = str(action) if action else "unknown"
        
        action_counter[action_type] += 1
        
        # Extract symbols
        symbols = step.get("symbols", [])
        if isinstance(symbols, list):
            for symbol in symbols:
                symbol_counter[symbol] += 1
        elif symbols:
            symbol_counter[str(symbols)] += 1
        
        # Track validity
        manifest_valid = step.get("manifest_valid", False)
        if manifest_valid:
            valid_rows += 1
        else:
            invalid_rows += 1
    
    total_runs = len(run_ids)
    total_steps = len(dataset)
    average_steps_per_run = (
        total_steps / total_runs if total_runs > 0 else 0.0
    )
    
    # Compute action proportions
    action_proportions: Dict[str, float] = {}
    if total_steps > 0:
        for action_type, count in action_counter.items():
            action_proportions[action_type] = round(count / total_steps, 4)
    
    # Build the report
    report: Dict[str, Any] = {
        "total_runs": total_runs,
        "total_steps": total_steps,
        "average_steps_per_run": round(average_steps_per_run, 2),
        "action_counts": dict(action_counter),
        "action_proportions": action_proportions,
        "symbol_counts": dict(symbol_counter),
        "integrity_summary": {
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "validity_rate": round(valid_rows / total_steps, 4) if total_steps > 0 else 0.0,
        },
        "heuristics": _compute_heuristics(dataset),
    }
    
    return report


def _compute_heuristics(dataset: list[dict]) -> Dict[str, Any]:
    """
    Compute trivial heuristic summaries from the dataset.
    
    This includes:
    - most_common_action: The most frequent action type
    - most_common_action_by_symbol: Most common action for each symbol
    - step_position_actions: Most common action at each step position
    
    Args:
        dataset: List of trajectory step dictionaries.
        
    Returns:
        Dictionary of heuristic summaries.
    """
    heuristics: Dict[str, Any] = {}
    
    if not dataset:
        return heuristics
    
    # Most common action overall
    action_counter = Counter()
    for step in dataset:
        action = step.get("action", {})
        if isinstance(action, dict):
            action_type = action.get("type", "unknown")
        else:
            action_type = str(action) if action else "unknown"
        action_counter[action_type] += 1
    
    if action_counter:
        most_common = action_counter.most_common(1)
        if most_common:
            heuristics["most_common_action"] = {
                "type": most_common[0][0],
                "count": most_common[0][1],
            }
    
    # Most common action by symbol
    symbol_actions: Dict[str, Counter] = {}
    for step in dataset:
        symbols = step.get("symbols", [])
        action = step.get("action", {})
        
        if isinstance(action, dict):
            action_type = action.get("type", "unknown")
        else:
            action_type = str(action) if action else "unknown"
        
        if not isinstance(symbols, list):
            symbols = [symbols] if symbols else []
        
        for symbol in symbols:
            if symbol not in symbol_actions:
                symbol_actions[symbol] = Counter()
            symbol_actions[symbol][action_type] += 1
    
    if symbol_actions:
        heuristics["most_common_action_by_symbol"] = {}
        for symbol, counter in symbol_actions.items():
            most_common = counter.most_common(1)
            if most_common:
                heuristics["most_common_action_by_symbol"][symbol] = {
                    "action": most_common[0][0],
                    "count": most_common[0][1],
                }
    
    # Most common action by step position (first 5 steps)
    step_position_actions: Dict[int, Counter] = {}
    for step in dataset:
        step_index = step.get("step_index", 0)
        if step_index < 5:  # Only track first 5 positions
            action = step.get("action", {})
            if isinstance(action, dict):
                action_type = action.get("type", "unknown")
            else:
                action_type = str(action) if action else "unknown"
            
            if step_index not in step_position_actions:
                step_position_actions[step_index] = Counter()
            step_position_actions[step_index][action_type] += 1
    
    if step_position_actions:
        heuristics["step_position_actions"] = {}
        for pos, counter in sorted(step_position_actions.items()):
            most_common = counter.most_common(1)
            if most_common:
                heuristics["step_position_actions"][pos] = {
                    "action": most_common[0][0],
                    "count": most_common[0][1],
                }
    
    return heuristics


def run_stub_learner(dataset_path: Path, output_path: Path) -> Path:
    """
    Run the stub learner on a trajectory dataset and produce a learning report.
    
    This function:
    1. Reads the exported JSONL dataset
    2. Computes aggregate statistics
    3. Writes the report to output_path
    
    Args:
        dataset_path: Path to the JSONL trajectory dataset.
        output_path: Path to write the learning report JSON.
        
    Returns:
        Path to the written report file.
        
    Raises:
        FileNotFoundError: If the dataset file doesn't exist.
    """
    from .replay import load_learning_dataset
    
    # Load the dataset
    dataset = load_learning_dataset(dataset_path)
    
    # Compute the report
    report = compute_learning_report(dataset)
    
    # Add metadata
    report["_metadata"] = {
        "dataset_path": str(dataset_path),
        "output_path": str(output_path),
    }
    
    # Write the report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure deterministic output (sorted keys)
    output_content = json.dumps(report, indent=2, sort_keys=True)
    if not output_content.endswith("\n"):
        output_content += "\n"
    
    output_path.write_text(output_content)
    
    return output_path
