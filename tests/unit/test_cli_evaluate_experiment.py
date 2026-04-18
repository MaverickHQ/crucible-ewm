"""Unit tests for CLI experiment evaluate command."""

import json
import tempfile
from pathlib import Path

import pytest

from services.cli.evaluate import experiment_evaluate_placeholder
from services.cli.main import build_parser


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


def _create_run_artifacts(run_dir: Path, run_id: str) -> None:
    """Helper to create minimal run artifacts in a directory."""
    manifest = _create_minimal_manifest(run_id)
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    
    decision = _create_minimal_decision(run_id)
    (run_dir / "decision.json").write_text(json.dumps(decision))
    
    trajectory = _create_minimal_trajectory(run_id)
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
    
    deltas = _create_minimal_deltas(run_id)
    (run_dir / "deltas.json").write_text(json.dumps(deltas))


class TestExperimentEvaluateCLI:
    """Tests for the CLI experiment evaluate command."""

    def test_happy_path(self):
        """Test 1: Happy path - valid experiment with 3 runs returns exit code 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)

            # Create 3 valid runs
            for i in range(1, 4):
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")

            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}\n")

            # Run CLI
            parser = build_parser()
            args = parser.parse_args([
                "experiment", "evaluate",
                "--experiment-dir", str(experiment_dir),
            ])
            exit_code = experiment_evaluate_placeholder(args)
            
            # Assert exit code 0
            assert exit_code == 0
            
            # Assert files exist
            json_path = experiment_dir / "evaluation_summary.json"
            csv_path = experiment_dir / "evaluation_summary.csv"
            assert json_path.exists()
            assert csv_path.exists()
            
            # Assert total_runs == 3
            content = json.loads(json_path.read_text())
            assert content["aggregate"]["total_runs"] == 3

    def test_integrity_failure_in_one_run(self):
        """Test 2: Integrity failure in one run returns exit code 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)

            # Create 2 valid runs
            run1_dir = experiment_dir / "artifacts" / "run-1"
            run2_dir = experiment_dir / "artifacts" / "run-2"
            run1_dir.mkdir(parents=True)
            run2_dir.mkdir(parents=True)
            _create_run_artifacts(run1_dir, "run-1")
            _create_run_artifacts(run2_dir, "run-2")

            # Create 1 run WITHOUT manifest (invalid)
            run3_dir = experiment_dir / "artifacts" / "run-3"
            run3_dir.mkdir(parents=True)
            # Only create some artifacts, not manifest
            (run3_dir / "decision.json").write_text(
                json.dumps(_create_minimal_decision("run-3"))
            )
            (run3_dir / "trajectory.json").write_text(
                json.dumps(_create_minimal_trajectory("run-3"))
            )
            (run3_dir / "deltas.json").write_text(
                json.dumps(_create_minimal_deltas("run-3"))
            )

            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}\n")

            # Run CLI
            parser = build_parser()
            args = parser.parse_args([
                "experiment", "evaluate",
                "--experiment-dir", str(experiment_dir),
            ])
            exit_code = experiment_evaluate_placeholder(args)
            
            # Assert exit code 2
            assert exit_code == 2
            
            # Assert runs_with_integrity_errors == 1
            json_path = experiment_dir / "evaluation_summary.json"
            content = json.loads(json_path.read_text())
            assert content["aggregate"]["runs_with_integrity_errors"] == 1

    def test_missing_results_jsonl(self):
        """Test 3: Missing results.jsonl returns exit code 2 with error code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)

            # Create one valid run
            run_dir = experiment_dir / "artifacts" / "run-1"
            run_dir.mkdir(parents=True)
            _create_run_artifacts(run_dir, "run-1")

            # Don't create results.jsonl

            # Run CLI
            parser = build_parser()
            args = parser.parse_args([
                "experiment", "evaluate",
                "--experiment-dir", str(experiment_dir),
            ])
            exit_code = experiment_evaluate_placeholder(args)

            # Assert exit code 2
            assert exit_code == 2

            # Assert integrity error contains results_jsonl_missing
            json_path = experiment_dir / "evaluation_summary.json"
            content = json.loads(json_path.read_text())
            assert "results_jsonl_missing" in content["integrity"]["integrity_errors"]

    def test_determinism(self):
        """Test 4: Running twice produces identical output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)

            # Create 3 valid runs
            for i in range(1, 4):
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")

            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}\n")

            # First run
            parser = build_parser()
            args = parser.parse_args([
                "experiment", "evaluate",
                "--experiment-dir", str(experiment_dir),
            ])
            experiment_evaluate_placeholder(args)

            json_path1 = experiment_dir / "evaluation_summary.json"
            content1 = json_path1.read_text()

            # Second run
            experiment_evaluate_placeholder(args)

            json_path2 = experiment_dir / "evaluation_summary.json"
            content2 = json_path2.read_text()

            # Assert identical
            assert content1 == content2

    def test_csv_column_order(self):
        """Test 5: CSV header has correct column order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir)

            # Create 2 valid runs
            for i in ["b", "a"]:
                run_dir = experiment_dir / "artifacts" / f"run-{i}"
                run_dir.mkdir(parents=True)
                _create_run_artifacts(run_dir, f"run-{i}")

            # Create results.jsonl
            (experiment_dir / "results.jsonl").write_text("{}\n")

            # Run CLI
            parser = build_parser()
            args = parser.parse_args([
                "experiment", "evaluate",
                "--experiment-dir", str(experiment_dir),
            ])
            experiment_evaluate_placeholder(args)

            # Check CSV
            csv_path = experiment_dir / "evaluation_summary.csv"
            content = csv_path.read_text()
            header = content.split("\n")[0]
            expected = (
                "run_id,manifest_valid,integrity_errors,"
                "steps_executed,truncated_by_budget"
            )
            assert header == expected


class TestCLIArgumentParsing:
    """Test CLI argument parsing for experiment evaluate."""

    def test_json_flag(self):
        """Test that --json flag is recognized."""
        parser = build_parser()
        # This should not raise
        args = parser.parse_args([
            "experiment", "evaluate",
            "--experiment-dir", "/tmp/foo", "--json",
        ])
        assert hasattr(args, "json")
        assert args.json is True

    def test_experiment_dir_required(self):
        """Test that --experiment-dir is required."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["experiment", "evaluate"])
