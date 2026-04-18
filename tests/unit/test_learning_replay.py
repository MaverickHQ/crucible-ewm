"""Tests for the learning replay module."""

import json
import tempfile
from pathlib import Path

import pytest

from services.core.learning.replay import (
    group_by_run,
    iter_trajectory_steps,
    load_learning_dataset,
)


@pytest.fixture
def temp_dataset_file():
    """Create a temporary JSONL dataset file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset.jsonl"
        
        # Write test data
        rows = [
            {
                "experiment_id": "test_exp",
                "run_id": "run-001",
                "step_index": 0,
                "action": {"type": "hold"},
                "symbols": ["AAPL"],
                "manifest_valid": True,
            },
            {
                "experiment_id": "test_exp",
                "run_id": "run-001",
                "step_index": 1,
                "action": {"type": "buy", "symbol": "AAPL"},
                "symbols": ["AAPL"],
                "manifest_valid": True,
            },
            {
                "experiment_id": "test_exp",
                "run_id": "run-002",
                "step_index": 0,
                "action": {"type": "sell"},
                "symbols": ["MSFT"],
                "manifest_valid": True,
            },
        ]
        
        with open(dataset_path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        
        yield dataset_path


def test_load_learning_dataset(temp_dataset_file):
    """Test loading entire dataset into memory."""
    dataset = load_learning_dataset(temp_dataset_file)
    
    assert len(dataset) == 3
    assert dataset[0]["run_id"] == "run-001"
    assert dataset[0]["step_index"] == 0
    assert dataset[1]["run_id"] == "run-001"
    assert dataset[2]["run_id"] == "run-002"


def test_iter_trajectory_steps(temp_dataset_file):
    """Test iterating over trajectory steps."""
    steps = list(iter_trajectory_steps(temp_dataset_file))
    
    assert len(steps) == 3
    assert steps[0]["step_index"] == 0
    assert steps[1]["step_index"] == 1
    assert steps[2]["run_id"] == "run-002"


def test_iter_trajectory_steps_empty_lines(temp_dataset_file):
    """Test iterator handles empty lines gracefully."""
    # Add empty lines to file
    with open(temp_dataset_file, "a") as f:
        f.write("\n\n")
    
    steps = list(iter_trajectory_steps(temp_dataset_file))
    
    # Should still return all 3 valid rows
    assert len(steps) == 3


def test_group_by_run(temp_dataset_file):
    """Test grouping steps by run_id."""
    dataset = load_learning_dataset(temp_dataset_file)
    runs = group_by_run(dataset)
    
    assert "run-001" in runs
    assert "run-002" in runs
    assert len(runs["run-001"]) == 2
    assert len(runs["run-002"]) == 1


def test_group_by_run_sorted_by_step_index(temp_dataset_file):
    """Test that steps within each run are sorted by step_index."""
    dataset = load_learning_dataset(temp_dataset_file)
    runs = group_by_run(dataset)
    
    # Steps should be sorted by step_index
    assert runs["run-001"][0]["step_index"] == 0
    assert runs["run-001"][1]["step_index"] == 1


def test_load_learning_dataset_missing_file():
    """Test error when dataset file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_learning_dataset(Path("/nonexistent/file.jsonl"))


def test_iter_trajectory_steps_missing_file():
    """Test error when dataset file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        list(iter_trajectory_steps(Path("/nonexistent/file.jsonl")))
