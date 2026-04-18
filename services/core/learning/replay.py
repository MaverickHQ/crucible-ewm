"""Replay module for iterating over exported trajectory datasets.

This module provides deterministic iteration over JSONL-formatted trajectory datasets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, List


def load_learning_dataset(path: Path) -> List[dict]:
    """
    Load the entire learning dataset into memory.
    
    Args:
        path: Path to the JSONL dataset file.
        
    Returns:
        List of trajectory step dictionaries.
        
    Raises:
        FileNotFoundError: If the dataset file doesn't exist.
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    
    dataset: List[dict] = []
    
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            dataset.append(json.loads(line))
    
    return dataset


def iter_trajectory_steps(path: Path) -> Iterator[dict]:
    """
    Iterate over trajectory steps in the dataset.
    
    Yields steps in deterministic file order (sorted by run_id, then step_index).
    This function reads line-by-line, so it's memory-efficient for large datasets.
    
    Args:
        path: Path to the JSONL dataset file.
        
    Yields:
        Trajectory step dictionaries.
        
    Raises:
        FileNotFoundError: If the dataset file doesn't exist.
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def group_by_run(dataset: List[dict]) -> dict[str, List[dict]]:
    """
    Group trajectory steps by run_id.
    
    Args:
        dataset: List of trajectory step dictionaries.
        
    Returns:
        Dictionary mapping run_id to list of steps for that run,
        sorted by step_index within each run.
    """
    runs: dict[str, List[dict]] = {}
    
    for step in dataset:
        run_id = step.get("run_id", "")
        if run_id not in runs:
            runs[run_id] = []
        runs[run_id].append(step)
    
    # Sort steps within each run by step_index
    for run_id in runs:
        runs[run_id].sort(key=lambda s: s.get("step_index", 0))
    
    return runs
