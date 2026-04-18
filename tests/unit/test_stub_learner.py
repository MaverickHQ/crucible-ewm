"""Tests for the stub learner module."""

import json
import tempfile
from pathlib import Path

import pytest

from ewm_core.learning.stub_learner import (
    compute_learning_report,
    run_stub_learner,
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
        ]
        
        with open(dataset_path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        
        yield dataset_path


@pytest.fixture
def sample_dataset():
    """Sample trajectory dataset for testing."""
    return [
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
            "run_id": "run-001",
            "step_index": 2,
            "action": {"type": "sell", "symbol": "AAPL"},
            "symbols": ["AAPL"],
            "manifest_valid": True,
        },
        {
            "experiment_id": "test_exp",
            "run_id": "run-002",
            "step_index": 0,
            "action": {"type": "hold"},
            "symbols": ["MSFT"],
            "manifest_valid": True,
        },
        {
            "experiment_id": "test_exp",
            "run_id": "run-002",
            "step_index": 1,
            "action": {"type": "buy", "symbol": "MSFT"},
            "symbols": ["MSFT"],
            "manifest_valid": True,
        },
    ]


def test_compute_learning_report_basic(sample_dataset):
    """Test basic report computation."""
    report = compute_learning_report(sample_dataset)
    
    assert report["total_runs"] == 2
    assert report["total_steps"] == 5
    assert report["average_steps_per_run"] == 2.5


def test_compute_learning_report_action_counts(sample_dataset):
    """Test action count aggregation."""
    report = compute_learning_report(sample_dataset)
    
    action_counts = report["action_counts"]
    assert action_counts.get("hold") == 2
    assert action_counts.get("buy") == 2
    assert action_counts.get("sell") == 1


def test_compute_learning_report_action_proportions(sample_dataset):
    """Test action proportion calculation."""
    report = compute_learning_report(sample_dataset)
    
    proportions = report["action_proportions"]
    # 5 total steps
    assert proportions.get("hold") == pytest.approx(0.4)
    assert proportions.get("buy") == pytest.approx(0.4)
    assert proportions.get("sell") == pytest.approx(0.2)


def test_compute_learning_report_symbol_counts(sample_dataset):
    """Test symbol count aggregation."""
    report = compute_learning_report(sample_dataset)
    
    symbol_counts = report["symbol_counts"]
    assert symbol_counts.get("AAPL") == 3
    assert symbol_counts.get("MSFT") == 2


def test_compute_learning_report_integrity_summary(sample_dataset):
    """Test integrity summary."""
    report = compute_learning_report(sample_dataset)
    
    integrity = report["integrity_summary"]
    assert integrity["valid_rows"] == 5
    assert integrity["invalid_rows"] == 0
    assert integrity["validity_rate"] == 1.0


def test_compute_learning_report_heuristics(sample_dataset):
    """Test heuristic computation."""
    report = compute_learning_report(sample_dataset)
    
    heuristics = report["heuristics"]
    
    # Most common action should be hold or buy (both have 2)
    assert "most_common_action" in heuristics
    
    # Most common action by symbol
    assert "most_common_action_by_symbol" in heuristics
    
    # Step position actions
    assert "step_position_actions" in heuristics


def test_compute_learning_report_empty_dataset():
    """Test report with empty dataset."""
    report = compute_learning_report([])
    
    assert report["total_runs"] == 0
    assert report["total_steps"] == 0
    assert report["average_steps_per_run"] == 0.0
    assert report["action_counts"] == {}
    assert report["symbol_counts"] == {}


def test_run_stub_learner(temp_dataset_file):
    """Test running stub learner end-to-end."""
    # Create temp dataset file
    dataset_path = Path(tempfile.mktemp(suffix=".jsonl"))
    
    rows = [
        {"run_id": "run-001", "step_index": 0, "action": {"type": "hold"}, "symbols": ["AAPL"], "manifest_valid": True},
        {"run_id": "run-001", "step_index": 1, "action": {"type": "buy"}, "symbols": ["AAPL"], "manifest_valid": True},
    ]
    
    with open(dataset_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    
    try:
        output_path = Path(tempfile.mktemp(suffix=".json"))
        
        result = run_stub_learner(dataset_path, output_path)
        
        assert result.exists()
        
        # Verify report content
        with open(result) as f:
            report = json.load(f)
        
        assert report["total_runs"] == 1
        assert report["total_steps"] == 2
        assert "action_counts" in report
        assert "heuristics" in report
        
    finally:
        if dataset_path.exists():
            dataset_path.unlink()


def test_stub_learner_deterministic_output():
    """Test that stub learner produces deterministic output."""
    dataset_path = Path(tempfile.mktemp(suffix=".jsonl"))
    
    rows = [
        {"run_id": "run-001", "step_index": i, "action": {"type": "hold"}, "symbols": ["AAPL"], "manifest_valid": True}
        for i in range(5)
    ]
    
    with open(dataset_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    
    try:
        output1 = Path(tempfile.mktemp(suffix=".json"))
        output2 = Path(tempfile.mktemp(suffix=".json"))
        
        run_stub_learner(dataset_path, output1)
        run_stub_learner(dataset_path, output2)
        
        with open(output1) as f1, open(output2) as f2:
            report1 = json.load(f1)
            report2 = json.load(f2)
        
        # Remove metadata which has different paths
        report1.pop("_metadata", None)
        report2.pop("_metadata", None)
        
        # Output should be identical (deterministic)
        assert report1 == report2
        
    finally:
        if dataset_path.exists():
            dataset_path.unlink()


def test_end_to_end_mini_test():
    """End-to-end test: dataset export -> learner report."""
    dataset_path = Path(tempfile.mktemp(suffix=".jsonl"))
    output_path = Path(tempfile.mktemp(suffix=".json"))
    
    # Create sample dataset
    dataset = [
        {"run_id": "run-A", "step_index": 0, "action": {"type": "hold"}, "symbols": ["X"], "manifest_valid": True},
        {"run_id": "run-A", "step_index": 1, "action": {"type": "buy"}, "symbols": ["X"], "manifest_valid": True},
        {"run_id": "run-B", "step_index": 0, "action": {"type": "sell"}, "symbols": ["Y"], "manifest_valid": True},
    ]
    
    with open(dataset_path, "w") as f:
        for row in dataset:
            f.write(json.dumps(row) + "\n")
    
    try:
        # Run stub learner
        result = run_stub_learner(dataset_path, output_path)
        
        # Verify
        assert result.exists()
        
        with open(result) as f:
            report = json.load(f)
        
        # Basic checks
        assert report["total_runs"] == 2
        assert report["total_steps"] == 3
        assert report["action_counts"]["hold"] == 1
        assert report["action_counts"]["buy"] == 1
        assert report["action_counts"]["sell"] == 1
        
    finally:
        if dataset_path.exists():
            dataset_path.unlink()
        if output_path.exists():
            output_path.unlink()
