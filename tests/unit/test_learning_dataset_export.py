"""Tests for the learning dataset export module."""

import json
import tempfile
from pathlib import Path

import pytest

from ewm_core.learning.dataset_export import (
    export_learning_dataset,
    load_run_manifest,
    load_run_trajectory,
)


@pytest.fixture
def temp_experiment_with_artifacts():
    """Create a temporary experiment directory with run artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "test_experiment"
        artifacts_dir = exp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        
        # Create evaluation_summary.json
        evaluation = {
            "aggregate": {"total_runs": 2, "runs_without_integrity_errors": 2},
            "runs": [
                {
                    "run_id": "run-001",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 3,
                    "truncated_by_budget": False,
                },
                {
                    "run_id": "run-002",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 2,
                    "truncated_by_budget": True,
                },
            ],
        }
        
        (exp_dir / "evaluation_summary.json").write_text(json.dumps(evaluation))
        
        # Create run-001 artifacts
        run1_dir = artifacts_dir / "run-001"
        run1_dir.mkdir()
        
        manifest1 = {
            "manifest_version": "2",
            "run_id": "run-001",
            "mode": "trading",
            "symbols": ["AAPL", "MSFT"],
            "strategy_path": "examples/strategies/threshold_demo.json",
        }
        (run1_dir / "manifest.json").write_text(json.dumps(manifest1))
        
        trajectory1 = [
            {"observation": {"step": 0}, "action": {"type": "hold"}, "done": False},
            {"observation": {"step": 1}, "action": {"type": "buy", "symbol": "AAPL"}, "done": False},
            {"observation": {"step": 2}, "action": {"type": "sell", "symbol": "AAPL"}, "done": True},
        ]
        (run1_dir / "trajectory.json").write_text(json.dumps(trajectory1))
        (run1_dir / "decision.json").write_text(json.dumps({"run_id": "run-001"}))
        (run1_dir / "deltas.json").write_text(json.dumps({"run_id": "run-001", "deltas": []}))
        
        # Create run-002 artifacts
        run2_dir = artifacts_dir / "run-002"
        run2_dir.mkdir()
        
        manifest2 = {
            "manifest_version": "2",
            "run_id": "run-002",
            "mode": "trading",
            "symbols": ["GOOG"],
            "strategy_path": "examples/strategies/sma_crossover_demo.json",
        }
        (run2_dir / "manifest.json").write_text(json.dumps(manifest2))
        
        trajectory2 = [
            {"observation": {"step": 0}, "action": {"type": "hold"}, "done": False},
            {"observation": {"step": 1}, "action": {"type": "buy", "symbol": "GOOG"}, "done": True},
        ]
        (run2_dir / "trajectory.json").write_text(json.dumps(trajectory2))
        (run2_dir / "decision.json").write_text(json.dumps({"run_id": "run-002"}))
        (run2_dir / "deltas.json").write_text(json.dumps({"run_id": "run-002", "deltas": []}))
        
        yield exp_dir


def test_load_run_manifest(temp_experiment_with_artifacts):
    """Test loading manifest from run directory."""
    artifacts_dir = temp_experiment_with_artifacts / "artifacts" / "run-001"
    manifest = load_run_manifest(artifacts_dir)
    
    assert manifest is not None
    assert manifest["run_id"] == "run-001"
    assert manifest["symbols"] == ["AAPL", "MSFT"]


def test_load_run_trajectory(temp_experiment_with_artifacts):
    """Test loading trajectory from run directory."""
    artifacts_dir = temp_experiment_with_artifacts / "artifacts" / "run-001"
    trajectory = load_run_trajectory(artifacts_dir)
    
    assert trajectory is not None
    assert len(trajectory) == 3
    assert trajectory[0]["action"]["type"] == "hold"


def test_export_learning_dataset(temp_experiment_with_artifacts):
    """Test exporting learning dataset."""
    output_path = Path(tempfile.mktemp(suffix=".jsonl"))
    
    try:
        result = export_learning_dataset(
            temp_experiment_with_artifacts,
            output_path,
            require_valid=True,
        )
        
        assert result.exists()
        
        # Read and verify rows
        rows = []
        with open(result) as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        
        # Should have 5 rows total (3 from run-001 + 2 from run-002)
        assert len(rows) == 5
        
        # Check first row structure
        row = rows[0]
        assert "experiment_id" in row
        assert "run_id" in row
        assert "step_index" in row
        assert "observation" in row
        assert "action" in row
        assert "next_observation" in row
        assert "done" in row
        assert "manifest_valid" in row
        assert "integrity_errors" in row
        assert "environment_type" in row
        assert "symbols" in row
        assert "metadata" in row
        
        # Check that data is correct
        assert row["experiment_id"] == "test_experiment"
        assert row["run_id"] == "run-001"
        assert row["step_index"] == 0
        assert row["symbols"] == ["AAPL", "MSFT"]
        
    finally:
        if output_path.exists():
            output_path.unlink()


def test_export_deterministic_ordering(temp_experiment_with_artifacts):
    """Test that exported dataset has deterministic ordering."""
    output_path1 = Path(tempfile.mktemp(suffix=".jsonl"))
    output_path2 = Path(tempfile.mktemp(suffix=".jsonl"))
    
    try:
        export_learning_dataset(
            temp_experiment_with_artifacts,
            output_path1,
            require_valid=True,
        )
        export_learning_dataset(
            temp_experiment_with_artifacts,
            output_path2,
            require_valid=True,
        )
        
        # Compare contents
        with open(output_path1) as f1, open(output_path2) as f2:
            assert f1.read() == f2.read()
        
    finally:
        if output_path1.exists():
            output_path1.unlink()
        if output_path2.exists():
            output_path2.unlink()


def test_export_missing_eval_file():
    """Test error when evaluation file is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "missing"
        exp_dir.mkdir()
        
        output_path = Path(tempfile.mktemp(suffix=".jsonl"))
        
        with pytest.raises(FileNotFoundError):
            export_learning_dataset(exp_dir, output_path)


def test_end_to_end_mini_test():
    """End-to-end test: valid experiment dir -> dataset export."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "mini_test"
        artifacts_dir = exp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        
        # Create minimal evaluation
        evaluation = {
            "aggregate": {"total_runs": 1, "runs_without_integrity_errors": 1},
            "runs": [
                {
                    "run_id": "test-run",
                    "manifest_valid": True,
                    "integrity_errors": [],
                    "steps_executed": 2,
                    "truncated_by_budget": False,
                },
            ],
        }
        (exp_dir / "evaluation_summary.json").write_text(json.dumps(evaluation))
        
        # Create minimal run
        run_dir = artifacts_dir / "test-run"
        run_dir.mkdir()
        
        manifest = {"manifest_version": "2", "run_id": "test-run", "symbols": ["AAPL"]}
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        
        trajectory = [
            {"observation": {}, "action": {"type": "hold"}, "done": False},
            {"observation": {}, "action": {"type": "buy"}, "done": True},
        ]
        (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (run_dir / "decision.json").write_text(json.dumps({"run_id": "test-run"}))
        (run_dir / "deltas.json").write_text(json.dumps({"run_id": "test-run", "deltas": []}))
        
        output_path = Path(tempfile.mktemp(suffix=".jsonl"))
        
        try:
            result = export_learning_dataset(exp_dir, output_path, require_valid=True)
            
            # Verify output
            assert result.exists()
            
            rows = []
            with open(result) as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
            
            assert len(rows) == 2
            assert rows[0]["run_id"] == "test-run"
            assert rows[0]["step_index"] == 0
            assert rows[1]["step_index"] == 1
            
        finally:
            if output_path.exists():
                output_path.unlink()
