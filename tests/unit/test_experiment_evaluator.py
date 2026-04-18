"""Unit tests for Experiment Evaluator."""

import json
import tempfile
from pathlib import Path

import pytest

from services.core.eval.experiment_evaluator import (
    evaluate_experiment,
    load_experiment_runs,
    write_experiment_evaluation,
)


def _create_minimal_manifest(run_id: str = "test-run-123") -> dict:
    """Create a minimal v2 manifest."""
    return {
        "manifest_version": "2",
        "run_id": run_id,
        "created_at": "2024-01-15T10:30:00+00:00",
        "runtime_version": "0.8.2.3",
        "mode": "agentcore-loop",
        "correlation_id": None,
        "strategy_path": "examples/fixtures/trading_path.json",
        "runtime_budgets": {},
        "policy_limits": {},
        "symbols": [],
    }


def _create_minimal_decision(run_id: str = "test-run-123") -> dict:
    """Create a minimal decision artifact."""
    return {
        "run_id": run_id,
        "approved": True,
        "rejected_step_index": None,
        "errors": [],
        "planner": {"planner_name": "test-planner", "planner_metadata": {}},
        "policy": {"policy_id": "test-policy", "policy_version": "1.0", "policy_hash": "abc123"},
    }


def _create_minimal_trajectory(run_id: str = "test-run-123") -> dict:
    """Create a minimal trajectory artifact."""
    return {
        "run_id": run_id,
        "trajectory": [],
        "steps": [],
    }


def _create_minimal_deltas(run_id: str = "test-run-123") -> dict:
    """Create a minimal deltas artifact."""
    return {
        "run_id": run_id,
        "deltas": [],
    }


def _create_run_artifacts(run_dir: Path, run_id: str, include_manifest: bool = True) -> None:
    """Helper to create minimal run artifacts in a directory."""
    if include_manifest:
        manifest = _create_minimal_manifest(run_id)
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
    
    decision = _create_minimal_decision(run_id)
    (run_dir / "decision.json").write_text(json.dumps(decision))
    
    trajectory = _create_minimal_trajectory(run_id)
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
    
    deltas = _create_minimal_deltas(run_id)
    (run_dir / "deltas.json").write_text(json.dumps(deltas))


class TestLoadExperimentRuns:
    """Tests for load_experiment_runs function."""

    def test_load_runs_from_artifacts_subdir(self):
        """Test loading runs from artifacts/ subdirectory (structure A)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create artifacts/run-1/ and artifacts/run-2/
            run1_dir = experiment_dir / "artifacts" / "run-1"
            run2_dir = experiment_dir / "artifacts" / "run-2"
            run1_dir.mkdir(parents=True)
            run2_dir.mkdir(parents=True)
            
            _create_run_artifacts(run1_dir, "run-1")
            _create_run_artifacts(run2_dir, "run-2")
            
            # Also create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Load runs
            runs = load_experiment_runs(experiment_dir)
            
            assert len(runs) == 2
            assert runs[0].name == "run-1"
            assert runs[1].name == "run-2"

    def test_load_runs_directly_in_experiment_dir(self):
        """Test loading runs directly in experiment directory (structure B)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create run-1/ and run-2/ directly
            run1_dir = experiment_dir / "run-aaa"
            run2_dir = experiment_dir / "run-bbb"
            run1_dir.mkdir()
            run2_dir.mkdir()
            
            _create_run_artifacts(run1_dir, "run-aaa")
            _create_run_artifacts(run2_dir, "run-bbb")
            
            # Also create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Load runs
            runs = load_experiment_runs(experiment_dir)
            
            assert len(runs) == 2
            assert runs[0].name == "run-aaa"
            assert runs[1].name == "run-bbb"

    def test_runs_sorted_by_id(self):
        """Test that runs are sorted by run_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create runs in non-alphabetical order
            run_c_dir = experiment_dir / "run-c"
            run_a_dir = experiment_dir / "run-a"
            run_b_dir = experiment_dir / "run-b"
            run_c_dir.mkdir()
            run_a_dir.mkdir()
            run_b_dir.mkdir()
            
            _create_run_artifacts(run_c_dir, "run-c")
            _create_run_artifacts(run_a_dir, "run-a")
            _create_run_artifacts(run_b_dir, "run-b")
            
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Load runs
            runs = load_experiment_runs(experiment_dir)
            
            assert len(runs) == 3
            assert runs[0].name == "run-a"
            assert runs[1].name == "run-b"
            assert runs[2].name == "run-c"

    def test_nonexistent_dir_raises(self):
        """Test that nonexistent directory raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "nonexistent"
            
            with pytest.raises(FileNotFoundError):
                load_experiment_runs(fake_dir)


class TestEvaluateExperiment:
    """Tests for evaluate_experiment function."""

    def test_evaluate_valid_experiment(self):
        """Test evaluating a valid experiment with multiple runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create 3 valid runs in artifacts/
            for i in range(1, 4):
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")
            
            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}\n")
            
            # Evaluate
            evaluation = evaluate_experiment(experiment_dir)
            
            # Check top-level keys exist
            assert "aggregate" in evaluation
            assert "integrity" in evaluation
            assert "runs" in evaluation
            assert "summary" in evaluation
            
            # Check aggregate
            assert evaluation["aggregate"]["total_runs"] == 3
            assert evaluation["aggregate"]["runs_with_integrity_errors"] == 0
            assert evaluation["aggregate"]["runs_without_integrity_errors"] == 3
            
            # Check integrity
            assert evaluation["integrity"]["experiment_dir_exists"] is True
            assert evaluation["integrity"]["results_jsonl_present"] is True
            assert evaluation["integrity"]["artifact_dirs_found"] == 3
            assert evaluation["integrity"]["integrity_errors"] == []
            
            # Check runs
            assert len(evaluation["runs"]) == 3
            for run in evaluation["runs"]:
                assert run["manifest_valid"] is True
                assert run["integrity_errors"] == []

    def test_missing_results_jsonl(self):
        """Test that missing results.jsonl is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create one valid run
            run_dir = experiment_dir / "artifacts" / "run-1"
            run_dir.mkdir(parents=True)
            _create_run_artifacts(run_dir, "run-1")
            
            # Don't create results.jsonl
            
            # Evaluate
            evaluation = evaluate_experiment(experiment_dir)
            
            # Check integrity error
            assert "results_jsonl_missing" in evaluation["integrity"]["integrity_errors"]
            assert evaluation["integrity"]["results_jsonl_present"] is False

    def test_run_with_missing_manifest(self):
        """Test that a run with missing manifest has integrity error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create one run WITHOUT manifest
            run_dir = experiment_dir / "artifacts" / "run-1"
            run_dir.mkdir(parents=True)
            # Create only non-manifest artifacts
            (run_dir / "decision.json").write_text(
                json.dumps(_create_minimal_decision("run-1"))
            )
            (run_dir / "trajectory.json").write_text(
                json.dumps(_create_minimal_trajectory("run-1"))
            )
            (run_dir / "deltas.json").write_text(
                json.dumps(_create_minimal_deltas("run-1"))
            )
            
            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Evaluate
            evaluation = evaluate_experiment(experiment_dir)
            
            # Check aggregate
            assert evaluation["aggregate"]["total_runs"] == 1
            assert evaluation["aggregate"]["runs_with_integrity_errors"] == 1
            
            # Check run has error
            assert len(evaluation["runs"]) == 1
            assert evaluation["runs"][0]["manifest_valid"] is False
            assert "manifest_missing" in evaluation["runs"][0]["integrity_errors"]


class TestWriteExperimentEvaluation:
    """Tests for write_experiment_evaluation function."""

    def test_write_json_and_csv(self):
        """Test writing JSON and CSV evaluation files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create valid experiment
            run_dir = experiment_dir / "artifacts" / "run-1"
            run_dir.mkdir(parents=True)
            _create_run_artifacts(run_dir, "run-1")
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Evaluate
            evaluation = evaluate_experiment(experiment_dir)
            
            # Write
            json_path, csv_path = write_experiment_evaluation(experiment_dir, evaluation)
            
            # Check files exist
            assert json_path.exists()
            assert csv_path.exists()
            
            # Verify JSON content
            json_content = json.loads(json_path.read_text())
            assert "aggregate" in json_content
            assert "runs" in json_content
            
            # Verify CSV content
            csv_content = csv_path.read_text()
            lines = csv_content.strip().split("\n")
            assert len(lines) == 2  # header + 1 row
            # Check header
            header = lines[0]
            expected = (
                "run_id,manifest_valid,integrity_errors,"
                "steps_executed,truncated_by_budget"
            )
            assert header == expected

    def test_csv_column_order(self):
        """Test that CSV has correct column order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create valid experiment with multiple runs
            for i in ["b", "a", "c"]:
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Evaluate
            evaluation = evaluate_experiment(experiment_dir)
            
            # Write
            _, csv_path = write_experiment_evaluation(experiment_dir, evaluation)
            
            # Check header order
            csv_content = csv_path.read_text()
            header = csv_content.split("\n")[0]
            expected = "run_id,manifest_valid,integrity_errors,steps_executed,truncated_by_budget"
            assert header == expected


class TestDeterminism:
    """Test determinism of experiment evaluation."""

    def test_deterministic_output(self):
        """Test that running evaluation twice produces identical output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create valid experiment
            for i in range(1, 4):
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # First evaluation
            evaluation1 = evaluate_experiment(experiment_dir)
            json_path1, _ = write_experiment_evaluation(experiment_dir, evaluation1)
            content1 = json_path1.read_text()
            
            # Second evaluation (should produce identical output)
            evaluation2 = evaluate_experiment(experiment_dir)
            json_path2, _ = write_experiment_evaluation(experiment_dir, evaluation2)
            content2 = json_path2.read_text()
            
            # Verify identical
            assert content1 == content2

    def test_sorted_runs_order(self):
        """Test that runs are always in sorted order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)
            
            # Create runs in random order
            for run_id in ["z-run", "a-run", "m-run"]:
                run_dir = experiment_dir / "artifacts" / run_id
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, run_id)
            (experiment_dir / "results.jsonl").write_text("{}")
            
            # Evaluate twice
            eval1 = evaluate_experiment(experiment_dir)
            runs1 = [r["run_id"] for r in eval1["runs"]]
            
            eval2 = evaluate_experiment(experiment_dir)
            runs2 = [r["run_id"] for r in eval2["runs"]]
            
            # Both should be sorted
            assert runs1 == ["a-run", "m-run", "z-run"]
            assert runs2 == runs1
