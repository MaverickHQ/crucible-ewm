"""Dataset export module for converting validated experiment trajectories to learning datasets.

This module converts validated experiment trajectories into a canonical learning-ready
JSONL dataset, with one row per trajectory step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .selector import select_learning_runs


def load_run_trajectory(run_dir: Path) -> Optional[List[Dict[str, Any]]]:
    """
    Load trajectory from a run's artifact directory.
    
    Args:
        run_dir: Path to the run's artifact directory.
        
    Returns:
        List of trajectory steps, or None if trajectory cannot be loaded.
    """
    trajectory_path = run_dir / "trajectory.json"
    
    if not trajectory_path.exists():
        return None
    
    try:
        with open(trajectory_path) as f:
            trajectory = json.load(f)
        
        # Handle different trajectory formats
        if isinstance(trajectory, list):
            return trajectory
        
        if isinstance(trajectory, dict):
            # Check for "tape" key
            if "tape" in trajectory and isinstance(trajectory["tape"], list):
                return trajectory["tape"]
            # Check for "trajectory" key
            if "trajectory" in trajectory and isinstance(trajectory["trajectory"], list):
                return trajectory["trajectory"]
        
        return None
    except (json.JSONDecodeError, OSError):
        return None


def load_run_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Load manifest from a run's artifact directory.
    
    Args:
        run_dir: Path to the run's artifact directory.
        
    Returns:
        Manifest dictionary, or None if not found.
    """
    manifest_path = run_dir / "manifest.json"
    
    if not manifest_path.exists():
        return None
    
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _extract_symbols(manifest: Optional[Dict[str, Any]]) -> List[str]:
    """Extract symbols from manifest."""
    if manifest and isinstance(manifest, dict):
        symbols = manifest.get("symbols", [])
        if isinstance(symbols, list):
            return symbols
    return []


def _extract_environment_type(manifest: Optional[Dict[str, Any]]) -> str:
    """Extract environment type from manifest, default to market_path."""
    if manifest and isinstance(manifest, dict):
        env_type = manifest.get("environment_type", "")
        if env_type:
            return env_type
    
    # Check mode for trading context
    if manifest and isinstance(manifest, dict):
        mode = manifest.get("mode", "")
        if mode in ("trading", "backtest", "simulation"):
            return "market_path"
    
    return "market_path"


def _build_trajectory_row(
    experiment_id: str,
    run_id: str,
    step_index: int,
    trajectory_step: Dict[str, Any],
    manifest: Optional[Dict[str, Any]],
    manifest_valid: bool,
    integrity_errors: List[str],
) -> Dict[str, Any]:
    """
    Build a single trajectory row for the learning dataset.
    
    Args:
        experiment_id: The experiment identifier.
        run_id: The run identifier.
        step_index: The step index in the trajectory.
        trajectory_step: The raw trajectory step data.
        manifest: The run manifest (may be None).
        manifest_valid: Whether the manifest is valid.
        integrity_errors: List of integrity errors for this run.
        
    Returns:
        A dictionary representing one row in the learning dataset.
    """
    symbols = _extract_symbols(manifest)
    environment_type = _extract_environment_type(manifest)
    
    # Extract observation and action from trajectory step
    # Different trajectory formats may store these differently
    observation = trajectory_step.get("observation", {})
    action = trajectory_step.get("action", {})
    next_observation = trajectory_step.get("next_observation", {})
    done = trajectory_step.get("done", False)
    
    # Build the row
    row: Dict[str, Any] = {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "step_index": step_index,
        "observation": observation,
        "action": action,
        "next_observation": next_observation,
        "done": done,
        "manifest_valid": manifest_valid,
        "integrity_errors": integrity_errors,
        "environment_type": environment_type,
        "symbols": symbols,
    }
    
    # Add metadata from manifest if available
    if manifest:
        row["metadata"] = {
            "run_id": manifest.get("run_id"),
            "mode": manifest.get("mode"),
            "runtime_version": manifest.get("runtime_version"),
            "strategy_path": manifest.get("strategy_path"),
        }
    else:
        row["metadata"] = {}
    
    return row


def export_learning_dataset(
    experiment_dir: Path,
    output_path: Path,
    *,
    require_valid: bool = True,
) -> Path:
    """
    Export validated experiment trajectories to a learning-ready JSONL dataset.
    
    This function:
    1. Selects runs based on structural validity (via selector)
    2. Loads trajectory data from each run's artifacts
    3. Exports one row per trajectory step in JSONL format
    
    Each row includes trading-oriented fields:
    - experiment_id, run_id, step_index
    - observation, action, next_observation, done
    - manifest_valid, integrity_errors
    - environment_type, symbols
    - metadata
    
    Args:
        experiment_dir: Path to the experiment directory.
        output_path: Path to write the JSONL dataset.
        require_valid: If True, only include structurally valid runs.
                      If False, include all selected runs.
    
    Returns:
        Path to the written dataset file.
        
    Raises:
        FileNotFoundError: If evaluation_summary.json doesn't exist.
    """
    experiment_dir = Path(experiment_dir)
    output_path = Path(output_path)
    
    # Get experiment ID from directory name
    experiment_id = experiment_dir.name
    
    # Select runs for learning
    selected_runs = select_learning_runs(
        experiment_dir,
        require_valid=require_valid,
        include_truncated=True,  # Include truncated runs for learning
    )
    
    # Determine artifact directory structure
    artifacts_dir = experiment_dir / "artifacts"
    
    # Build trajectory rows
    rows: List[Dict[str, Any]] = []
    
    for run in selected_runs:
        run_id = run.get("run_id", "")
        manifest_valid = run.get("manifest_valid", False)
        integrity_errors = run.get("integrity_errors", [])
        
        # Find the run directory
        run_dir: Optional[Path] = None
        
        if artifacts_dir.exists():
            # Structure A: artifacts/<run_id>/
            potential_dir = artifacts_dir / run_id
            if potential_dir.exists() and potential_dir.is_dir():
                run_dir = potential_dir
        
        if run_dir is None:
            # Structure B: <run_id>/ directly in experiment_dir
            potential_dir = experiment_dir / run_id
            if potential_dir.exists() and potential_dir.is_dir():
                run_dir = potential_dir
        
        if run_dir is None:
            # Skip if we can't find the run directory
            continue
        
        # Load manifest and trajectory
        manifest = load_run_manifest(run_dir)
        trajectory = load_run_trajectory(run_dir)
        
        if trajectory is None:
            # Skip if we can't load trajectory
            continue
        
        # Build rows for each step
        for step_index, step_data in enumerate(trajectory):
            row = _build_trajectory_row(
                experiment_id=experiment_id,
                run_id=run_id,
                step_index=step_index,
                trajectory_step=step_data,
                manifest=manifest,
                manifest_valid=manifest_valid,
                integrity_errors=integrity_errors,
            )
            rows.append(row)
    
    # Sort rows deterministically by run_id, then step_index
    rows.sort(key=lambda r: (r.get("run_id", ""), r.get("step_index", 0)))
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write JSONL
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    
    return output_path
