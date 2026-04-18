"""Tests for the learning selector module."""

import json
import tempfile
from pathlib import Path

import pytest

from services.core.learning.selector import (
    load_evaluation_runs,
    select_learning_runs,
)


@pytest.fixture
def temp_experiment_dir():
    """Create a temporary experiment directory with evaluation data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "test_experiment"
        exp_dir.mkdir()
        
        # Create evaluation_summary.json
        evaluation = {
            "aggregate": {
                "total_runs": 5,
                "runs_with_integrity_errors": 2,
                "runs_without_integrity_errors": 3,
            },
            "runs": [
                {
                    "run_id": "run-001",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 10,
                    "truncated_by_budget": False,
                },
                {
                    "run_id": "run-002",
                    "manifest_valid": False,
                    "integrity_errors": ["missing_manifest"],
                    "steps_executed": None,
                    "truncated_by_budget": None,
                },
                {
                    "run_id": "run-003",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 5,
                    "truncated_by_budget": True,  # truncated
                },
                {
                    "run_id": "run-004",
                    "manifest_valid": True,
                    "integrity_errors": ["corrupted_trajectory"],
                    "steps_executed": 8,
                    "truncated_by_budget": False,
                },
                {
                    "run_id": "run-005",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 3,
                    "truncated_by_budget": False,
                },
            ],
        }
        
        (exp_dir / "evaluation_summary.json").write_text(json.dumps(evaluation))
        
        yield exp_dir


def test_load_evaluation_runs(temp_experiment_dir):
    """Test loading runs from evaluation summary."""
    runs = load_evaluation_runs(temp_experiment_dir)
    
    assert len(runs) == 5
    # Should be sorted by run_id
    assert runs[0]["run_id"] == "run-001"
    assert runs[4]["run_id"] == "run-005"


def test_select_learning_runs_default(temp_experiment_dir):
    """Test default selection - only valid runs, include truncated."""
    selected = select_learning_runs(
        temp_experiment_dir,
        require_valid=True,
        include_truncated=True,
    )
    
    # Should include run-001 (valid), run-003 (valid + truncated), run-005 (valid)
    # run-002 is invalid, run-004 has integrity errors
    assert len(selected) == 3
    run_ids = [r["run_id"] for r in selected]
    assert "run-001" in run_ids
    assert "run-003" in run_ids  # included because include_truncated=True
    assert "run-005" in run_ids


def test_select_learning_runs_exclude_truncated(temp_experiment_dir):
    """Test excluding truncated runs."""
    selected = select_learning_runs(
        temp_experiment_dir,
        require_valid=True,
        include_truncated=False,
    )
    
    # Should only include run-001 and run-005 (not run-003 which is truncated)
    assert len(selected) == 2
    run_ids = [r["run_id"] for r in selected]
    assert "run-001" in run_ids
    assert "run-003" not in run_ids  # excluded because truncated
    assert "run-005" in run_ids


def test_select_learning_runs_no_valid_required(temp_experiment_dir):
    """Test selection without requiring valid runs."""
    selected = select_learning_runs(
        temp_experiment_dir,
        require_valid=False,
        include_truncated=True,
    )
    
    # Should include all runs
    assert len(selected) == 5


def test_select_learning_runs_missing_eval_file():
    """Test error when evaluation file is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "missing"
        exp_dir.mkdir()
        
        with pytest.raises(FileNotFoundError):
            select_learning_runs(exp_dir)


def test_deterministic_ordering(temp_experiment_dir):
    """Test that results are deterministically ordered by run_id."""
    selected1 = select_learning_runs(temp_experiment_dir)
    selected2 = select_learning_runs(temp_experiment_dir)
    
    run_ids1 = [r["run_id"] for r in selected1]
    run_ids2 = [r["run_id"] for r in selected2]
    
    assert run_ids1 == run_ids2
