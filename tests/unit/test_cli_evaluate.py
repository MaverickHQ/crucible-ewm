"""Tests for the CLI evaluate module."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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
    """Create a minimal trajectory artifact (as list)."""
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


class TestRunEvaluateHappyPath:
    """Tests for happy path evaluation."""

    def test_happy_path_valid_artifact_dir(self, tmp_path: Path) -> None:
        """Test 1: Happy path with valid artifact dir."""
        # Create temp artifact dir with minimal valid manifest + trajectory
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        # Write minimal artifacts
        manifest = _create_minimal_manifest("test-run-123")
        decision = _create_minimal_decision("test-run-123")
        trajectory = _create_minimal_trajectory("test-run-123")
        deltas = _create_minimal_deltas("test-run-123")

        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / "decision.json").write_text(json.dumps(decision))
        (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (artifact_dir / "deltas.json").write_text(json.dumps(deltas))

        # Call CLI via subprocess
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(artifact_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert evaluation.json exists
        eval_file = artifact_dir / "evaluation.json"
        assert eval_file.exists(), "evaluation.json should exist"

        # Assert output contains "Manifest valid: True"
        assert "Manifest valid: True" in result.stdout, (
            f"Expected 'Manifest valid: True' in output, got: {result.stdout}"
        )

    def test_json_flag_outputs_json(self, tmp_path: Path) -> None:
        """Test 3: --json flag outputs valid JSON to stdout."""
        # Create temp artifact dir with minimal valid manifest + trajectory
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        # Write minimal artifacts
        manifest = _create_minimal_manifest("test-run-123")
        decision = _create_minimal_decision("test-run-123")
        trajectory = _create_minimal_trajectory("test-run-123")
        deltas = _create_minimal_deltas("test-run-123")

        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / "decision.json").write_text(json.dumps(decision))
        (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (artifact_dir / "deltas.json").write_text(json.dumps(deltas))

        # Call CLI with --json flag
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(artifact_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert printed output parses as JSON
        # The output has both the JSON and the summary, need to find where JSON ends
        # JSON will start with { and contain "constraint", "integrity", etc.
        # Strip leading whitespace and find JSON
        output = result.stdout.lstrip()
        json_output = None

        if output.startswith("{"):
            # Find the closing brace of the top-level JSON object
            # by tracking nesting depth
            depth = 0
            json_end = None
            for i, char in enumerate(output):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break

            if json_end:
                json_text = output[:json_end]
                try:
                    json_output = json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        assert json_output is not None, f"Could not find JSON in output: {result.stdout}"
        assert "integrity" in json_output
        assert "structure" in json_output
        assert "constraint" in json_output

        # Confirm evaluation.json still written
        eval_file = artifact_dir / "evaluation.json"
        assert eval_file.exists(), "evaluation.json should exist"


class TestRunEvaluateIntegrityFailure:
    """Tests for integrity failure cases."""

    def test_missing_manifest_returns_exit_code_2(self, tmp_path: Path) -> None:
        """Test 2: Integrity failure case - remove manifest.json."""
        # Create temp artifact dir without manifest.json
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        # Write only non-manifest artifacts
        decision = _create_minimal_decision("test-run-123")
        trajectory = _create_minimal_trajectory("test-run-123")
        deltas = _create_minimal_deltas("test-run-123")

        (artifact_dir / "decision.json").write_text(json.dumps(decision))
        (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (artifact_dir / "deltas.json").write_text(json.dumps(deltas))

        # Run CLI
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(artifact_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 2
        assert result.returncode == 2, (
            f"Expected exit code 2, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert output contains "manifest_missing"
        assert "manifest_missing" in result.stdout, (
            f"Expected 'manifest_missing' in output, got: {result.stdout}"
        )


class TestRunEvaluateHelp:
    """Tests for help command."""

    def test_help_works_without_optional_deps(self) -> None:
        """Test 4: Help works without optional deps."""
        # Run help
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
        )

        # Help should show the correct description
        assert "artifacts-dir" in result.stdout.lower() or "artifacts" in result.stdout.lower()


class TestRunEvaluateDeterminism:
    """Tests for deterministic output."""

    def test_deterministic_cli_output(self, tmp_path: Path) -> None:
        """Test 5: Deterministic CLI output - run twice, hash identical."""
        # Create temp artifact dir
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        # Write minimal artifacts
        manifest = _create_minimal_manifest("test-run-123")
        decision = _create_minimal_decision("test-run-123")
        trajectory = _create_minimal_trajectory("test-run-123")
        deltas = _create_minimal_deltas("test-run-123")

        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / "decision.json").write_text(json.dumps(decision))
        (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (artifact_dir / "deltas.json").write_text(json.dumps(deltas))

        # First run
        result1 = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(artifact_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result1.returncode == 0

        # Read evaluation.json after first run
        eval_file1 = artifact_dir / "evaluation.json"
        content1 = eval_file1.read_text()

        # Second run - need to use a fresh artifact dir since we reuse the same one
        artifact_dir2 = tmp_path / "artifacts2"
        artifact_dir2.mkdir()

        (artifact_dir2 / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir2 / "decision.json").write_text(json.dumps(decision))
        (artifact_dir2 / "trajectory.json").write_text(json.dumps(trajectory))
        (artifact_dir2 / "deltas.json").write_text(json.dumps(deltas))

        result2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(artifact_dir2),
            ],
            capture_output=True,
            text=True,
        )
        assert result2.returncode == 0

        # Read evaluation.json after second run
        eval_file2 = artifact_dir2 / "evaluation.json"
        content2 = eval_file2.read_text()

        # Hash and assert identical
        assert content1 == content2, "Output should be byte-for-byte identical"


class TestExperimentEvaluate:
    """Tests for experiment evaluate command (R22)."""

    def test_experiment_evaluate_with_valid_runs(self, tmp_path: Path) -> None:
        """Test 6: experiment evaluate with 2 valid runs returns exit code 0."""
        # Create temp experiment dir with 2 valid runs
        exp_dir = tmp_path / "experiment"
        exp_dir.mkdir()

        # Create artifacts directory structure: artifacts/<run_id>/
        artifacts_dir = exp_dir / "artifacts"
        
        # Create 2 valid runs
        for i in range(1, 3):
            run_dir = artifacts_dir / f"run-{i}"
            run_dir.mkdir(parents=True)
            
            # Write minimal artifacts
            manifest = _create_minimal_manifest(f"run-{i}")
            decision = _create_minimal_decision(f"run-{i}")
            trajectory = _create_minimal_trajectory(f"run-{i}")
            deltas = _create_minimal_deltas(f"run-{i}")

            (run_dir / "manifest.json").write_text(json.dumps(manifest))
            (run_dir / "decision.json").write_text(json.dumps(decision))
            (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (run_dir / "deltas.json").write_text(json.dumps(deltas))

        # Create results.jsonl (required)
        (exp_dir / "results.jsonl").write_text("{}\n")

        # Run CLI
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "experiment",
                "evaluate",
                "--experiment-dir",
                str(exp_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. "
            f"stderr: {result.stderr}, stdout: {result.stdout}"
        )

        # Assert stdout contains "Total runs: 2"
        assert "Total runs: 2" in result.stdout, (
            f"Expected 'Total runs: 2' in output, got: {result.stdout}"
        )

        # Assert evaluation_summary.json exists
        json_path = exp_dir / "evaluation_summary.json"
        assert json_path.exists(), "evaluation_summary.json should exist"

        # Assert evaluation_summary.csv exists
        csv_path = exp_dir / "evaluation_summary.csv"
        assert csv_path.exists(), "evaluation_summary.csv should exist"

    def test_experiment_evaluate_json_flag(self, tmp_path: Path) -> None:
        """Test 7: experiment evaluate --json outputs valid JSON."""
        # Create temp experiment dir with 1 valid run
        exp_dir = tmp_path / "experiment"
        exp_dir.mkdir()

        # Create artifacts directory
        artifacts_dir = exp_dir / "artifacts"
        
        # Create 1 valid run
        run_dir = artifacts_dir / "run-1"
        run_dir.mkdir(parents=True)
        
        manifest = _create_minimal_manifest("run-1")
        decision = _create_minimal_decision("run-1")
        trajectory = _create_minimal_trajectory("run-1")
        deltas = _create_minimal_deltas("run-1")

        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "decision.json").write_text(json.dumps(decision))
        (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (run_dir / "deltas.json").write_text(json.dumps(deltas))

        # Create results.jsonl
        (exp_dir / "results.jsonl").write_text("{}\n")

        # Run CLI with --json flag
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "experiment",
                "evaluate",
                "--experiment-dir",
                str(exp_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
        )

        # Parse stdout as JSON
        output = result.stdout.lstrip()
        json_output = None

        if output.startswith("{"):
            # Find the closing brace of the top-level JSON object
            depth = 0
            json_end = None
            for i, char in enumerate(output):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break

            if json_end:
                json_text = output[:json_end]
                try:
                    json_output = json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        assert json_output is not None, f"Could not find JSON in output: {result.stdout}"
        
        # Assert JSON contains expected keys
        assert "aggregate" in json_output
        assert "integrity" in json_output
        
        # Assert aggregate.total_runs == 1
        aggregate = json_output.get("aggregate", {})
        assert aggregate.get("total_runs") == 1, (
            f"Expected total_runs == 1, got: {aggregate.get('total_runs')}"
        )


class TestRunEvaluateWithRunId:
    """Tests for --run-id functionality."""

    def test_evaluate_with_run_id_resolves_subdir(self, tmp_path: Path) -> None:
        """Test: --run-id resolves subdirectory under artifacts root."""
        # Create temp root dir
        root_dir = tmp_path / "artifacts_root"
        root_dir.mkdir()

        # Create subdir with run ID
        run_id = "test-run-456"
        run_dir = root_dir / run_id
        run_dir.mkdir()

        # Write minimal artifacts in subdir
        manifest = _create_minimal_manifest(run_id)
        decision = _create_minimal_decision(run_id)
        trajectory = _create_minimal_trajectory(run_id)
        deltas = _create_minimal_deltas(run_id)

        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "decision.json").write_text(json.dumps(decision))
        (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
        (run_dir / "deltas.json").write_text(json.dumps(deltas))

        # Call CLI with --run-id
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(root_dir),
                "--run-id",
                run_id,
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 0
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert evaluation.json exists in subdir (root/run_id/)
        eval_file = run_dir / "evaluation.json"
        assert eval_file.exists(), "evaluation.json should exist in run subdirectory"

        # Assert output contains "Manifest valid: True"
        assert "Manifest valid: True" in result.stdout, (
            f"Expected 'Manifest valid: True' in output, got: {result.stdout}"
        )

    def test_evaluate_with_run_id_missing_dir_returns_2(self, tmp_path: Path) -> None:
        """Test: --run-id with missing subdir returns exit code 2 and run_dir_missing."""
        # Create temp root dir WITHOUT subdir
        root_dir = tmp_path / "artifacts_root"
        root_dir.mkdir()

        run_id = "non-existent-run"

        # Call CLI with --run-id but no subdir
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(root_dir),
                "--run-id",
                run_id,
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 2
        assert result.returncode == 2, (
            f"Expected exit code 2, got {result.returncode}. stderr: {result.stderr}"
        )

        # Assert output contains "run_dir_missing"
        assert "run_dir_missing" in result.stdout, (
            f"Expected 'run_dir_missing' in output, got: {result.stdout}"
        )

    def test_json_output_on_run_dir_missing_is_valid_json(self, tmp_path: Path) -> None:
        """Test: --json flag outputs valid JSON when run dir is missing."""
        # Create temp root dir WITHOUT subdir
        root_dir = tmp_path / "artifacts_root"
        root_dir.mkdir()

        run_id = "non-existent-run"

        # Call CLI with --run-id and --json
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.cli.main",
                "run",
                "evaluate",
                "--artifacts-dir",
                str(root_dir),
                "--run-id",
                run_id,
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Assert exit code 2
        assert result.returncode == 2, (
            f"Expected exit code 2, got {result.returncode}. stderr: {result.stderr}"
        )

        # Parse stdout as JSON
        output = result.stdout.lstrip()
        json_output = None

        if output.startswith("{"):
            # Find the closing brace of the top-level JSON object
            depth = 0
            json_end = None
            for i, char in enumerate(output):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break

            if json_end:
                json_text = output[:json_end]
                try:
                    json_output = json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        assert json_output is not None, f"Could not find JSON in output: {result.stdout}"

        # Assert integrity_errors contains run_dir_missing
        integrity = json_output.get("integrity", {})
        assert "run_dir_missing" in integrity.get("integrity_errors", []), (
            f"Expected 'run_dir_missing' in integrity_errors, got: {integrity}"
        )

        # Assert integrity_error_details contains the error
        error_details = integrity.get("integrity_error_details", [])
        assert any(e.get("code") == "run_dir_missing" for e in error_details), (
            f"Expected run_dir_missing in error_details, got: {error_details}"
        )

        # Assert top-level keys are in correct order: constraint, integrity, run_id, structure
        keys = list(json_output.keys())
        expected_order = ["constraint", "integrity", "run_id", "structure"]
        assert keys == expected_order, (
            f"Expected keys in order {expected_order}, got: {keys}"
        )
