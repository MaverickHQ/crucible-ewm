"""Unit tests for Run Evaluator."""

import json
import tempfile
from pathlib import Path

import pytest

from services.core.eval.run_evaluator import (
    evaluate_run,
    load_run_artifacts,
    write_evaluation,
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


class TestLoadRunArtifacts:
    """Tests for load_run_artifacts function."""

    def test_load_all_artifacts(self):
        """Test loading all required artifact files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Write minimal artifacts
            manifest = _create_minimal_manifest()
            decision = _create_minimal_decision()
            trajectory = _create_minimal_trajectory()
            deltas = _create_minimal_deltas()
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load artifacts
            artifacts = load_run_artifacts(artifact_dir)
            
            assert "manifest" in artifacts
            assert "decision" in artifacts
            assert "trajectory" in artifacts
            assert "deltas" in artifacts
            assert artifacts["manifest"]["run_id"] == "test-run-123"

    def test_missing_manifest_returns_partial(self):
        """Test that missing manifest.json does not raise error, returns partial dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Write only some artifacts
            (artifact_dir / "decision.json").write_text(json.dumps(_create_minimal_decision()))
            (artifact_dir / "trajectory.json").write_text(json.dumps(_create_minimal_trajectory()))
            (artifact_dir / "deltas.json").write_text(json.dumps(_create_minimal_deltas()))
            
            # Should NOT raise - returns partial artifacts
            artifacts = load_run_artifacts(artifact_dir)
            
            # Only decision, trajectory, deltas should be present
            assert "manifest" not in artifacts
            assert "decision" in artifacts
            assert "trajectory" in artifacts
            assert "deltas" in artifacts

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises JSONDecodeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Write invalid JSON to manifest
            (artifact_dir / "manifest.json").write_text("{invalid json")
            (artifact_dir / "decision.json").write_text(json.dumps(_create_minimal_decision()))
            (artifact_dir / "trajectory.json").write_text(json.dumps(_create_minimal_trajectory()))
            (artifact_dir / "deltas.json").write_text(json.dumps(_create_minimal_deltas()))
            
            with pytest.raises(json.JSONDecodeError):
                load_run_artifacts(artifact_dir)


class TestEvaluateRun:
    """Tests for evaluate_run function."""

    def test_minimal_valid_artifact_dir(self):
        """Test 1: Minimal valid artifact dir with v2 manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal valid artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify manifest_valid is true
            assert evaluation["integrity"]["manifest_valid"] is True
            assert evaluation["integrity"]["manifest_version"] == "2"
            assert evaluation["integrity"]["required_files_present"] is True
            assert evaluation["integrity"]["run_id_consistent"] is True
            assert evaluation["integrity"]["integrity_errors"] == []
            # Verify integrity_error_details is present and empty
            assert "integrity_error_details" in evaluation["integrity"]
            assert evaluation["integrity"]["integrity_error_details"] == []

    def test_wrong_manifest_version(self):
        """Test 2: Wrong manifest_version => manifest_valid false + error code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create manifest with wrong version
            manifest = _create_minimal_manifest("run-123")
            manifest["manifest_version"] = "1"
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify manifest_valid is false
            assert evaluation["integrity"]["manifest_valid"] is False
            # Check error code is present
            assert "manifest_version_mismatch" in evaluation["integrity"]["integrity_errors"]
            # Check integrity_error_details also has the error
            assert "integrity_error_details" in evaluation["integrity"]
            detail_codes = [d["code"] for d in evaluation["integrity"]["integrity_error_details"]]
            assert "manifest_version_mismatch" in detail_codes

    def test_missing_file(self):
        """Test 3: Missing file (e.g., deltas.json) => required_files_present false."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create only some artifacts (missing deltas.json)
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify required_files_present is false
            assert evaluation["integrity"]["required_files_present"] is False
            # Check error code is present
            assert "required_files_missing" in evaluation["integrity"]["integrity_errors"]
            # Check integrity_error_details also has the error
            detail_codes = [d["code"] for d in evaluation["integrity"]["integrity_error_details"]]
            assert "required_files_missing" in detail_codes

    def test_trajectory_schema_list(self):
        """Test 4a: Trajectory as list => steps_executed computed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            # Trajectory as a list with 5 items
            trajectory = [
                {"step": 0},
                {"step": 1},
                {"step": 2},
                {"step": 3},
                {"step": 4},
            ]
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify steps_executed
            assert evaluation["structure"]["steps_executed"] == 5

    def test_trajectory_schema_dict_with_tape(self):
        """Test 4b: Trajectory as dict with tape => steps_executed computed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            # Trajectory as dict with "tape" key
            trajectory = {
                "run_id": "run-123",
                "tape": [
                    {"step": 0},
                    {"step": 1},
                    {"step": 2},
                ],
            }
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify steps_executed
            assert evaluation["structure"]["steps_executed"] == 3

    def test_trajectory_schema_unknown(self):
        """Test 4c: Unknown trajectory schema => steps_executed is null and warning present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            # Trajectory with unknown schema
            trajectory = {
                "run_id": "run-123",
                "unknown_key": "some_value",
            }
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify steps_executed is null and warning is present
            assert evaluation["structure"]["steps_executed"] is None
            assert "integrity_warnings" in evaluation
            assert len(evaluation["integrity_warnings"]) > 0
            assert "trajectory schema unknown" in evaluation["integrity_warnings"][0]

    def test_truncated_by_budget_at_max(self):
        """Test truncated_by_budget is True when steps == max_steps (structural truncation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create manifest with max_steps = 5
            manifest = _create_minimal_manifest("run-123")
            manifest["runtime_budgets"] = {"max_steps": 5}
            
            # Trajectory with exactly 5 steps (equal to max_steps)
            trajectory = {
                "run_id": "run-123",
                "trajectory": [{}, {}, {}, {}, {}],  # 5 items
            }
            decision = _create_minimal_decision("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify truncated_by_budget is True (stopped at max_steps = structural truncation)
            # Check both keys: new canonical + deprecated
            assert evaluation["constraint"]["runtime_budgets_max_steps"] == 5
            assert evaluation["constraint"]["runtime_budget_max_steps"] == 5  # Deprecated key
            assert evaluation["constraint"]["truncated_by_budget"] is True

    def test_not_truncated_by_budget_under_max(self):
        """Test truncated_by_budget is False when steps < max_steps (ended naturally)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create manifest with max_steps = 10
            manifest = _create_minimal_manifest("run-123")
            manifest["runtime_budgets"] = {"max_steps": 10}
            
            # Trajectory with 5 steps (less than max_steps)
            trajectory = {
                "run_id": "run-123",
                "trajectory": [{}, {}, {}, {}, {}],  # 5 items
            }
            decision = _create_minimal_decision("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify truncated_by_budget is False (ended naturally before budget exhausted)
            # Check both keys: new canonical + deprecated
            assert evaluation["constraint"]["runtime_budgets_max_steps"] == 10
            assert evaluation["constraint"]["runtime_budget_max_steps"] == 10  # Deprecated key
            assert evaluation["constraint"]["truncated_by_budget"] is False


class TestWriteEvaluation:
    """Tests for write_evaluation function."""

    def test_write_evaluation_json(self):
        """Test writing evaluation.json to artifact directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load, evaluate, and write
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            output_path = write_evaluation(artifact_dir, evaluation)
            
            # Verify file exists
            assert output_path.exists()
            assert output_path.name == "evaluation.json"
            
            # Verify content is valid JSON
            content = json.loads(output_path.read_text())
            assert content["run_id"] == "run-123"
            assert "integrity" in content
            assert "structure" in content
            assert "constraint" in content

    def test_newline_at_eof(self):
        """Test that evaluation.json ends with newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load, evaluate, and write
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            output_path = write_evaluation(artifact_dir, evaluation)
            
            # Verify newline at EOF
            content = output_path.read_text()
            assert content.endswith("\n")


class TestDeterminism:
    """Test 5: Determinism - run evaluator twice on same inputs => file content identical."""

    def test_no_evaluated_at_field(self):
        """Test that evaluated_at field is NOT present in evaluation output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify evaluated_at is NOT present
            assert "evaluated_at" not in evaluation, "evaluated_at should not be present"

    def test_deterministic_output(self):
        """Test that running the evaluator twice produces identical output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # First run
            artifacts1 = load_run_artifacts(artifact_dir)
            evaluation1 = evaluate_run(artifacts1, artifact_dir=artifact_dir)
            output_path1 = write_evaluation(artifact_dir, evaluation1)
            content1 = output_path1.read_text()
            
            # Second run (reload from disk)
            # Need to clear and re-create for second run to simulate fresh load
            artifacts2 = load_run_artifacts(artifact_dir)
            evaluation2 = evaluate_run(artifacts2, artifact_dir=artifact_dir)
            output_path2 = write_evaluation(artifact_dir, evaluation2)
            content2 = output_path2.read_text()
            
            # Verify content is BYTE-FOR-BYTE identical
            assert content1 == content2, "Output should be byte-for-byte identical"
            
            # Also verify evaluated_at is not in output
            assert "evaluated_at" not in content1

    def test_sorted_keys(self):
        """Test that output JSON has sorted keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create minimal artifacts
            manifest = _create_minimal_manifest("run-123")
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load, evaluate, and write
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            output_path = write_evaluation(artifact_dir, evaluation)
            
            # Verify keys are sorted
            content = output_path.read_text()
            parsed = json.loads(content)
            
            # Top-level keys should be sorted
            keys = list(parsed.keys())
            assert keys == sorted(keys), f"Keys are not sorted: {keys}"
            
            # Nested keys should also be sorted
            for section in ["integrity", "structure", "constraint"]:
                if section in parsed:
                    section_keys = list(parsed[section].keys())
                    assert section_keys == sorted(section_keys), (
                        f"{section} keys are not sorted: {section_keys}"
                    )


class TestManifestMissing:
    """Test error handling when manifest is missing or invalid."""

    def test_missing_manifest_integrity_errors(self):
        """Test that missing manifest results in integrity errors in evaluation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create only non-manifest artifacts
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load should NOT raise - returns partial artifacts
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify manifest_valid is false
            assert evaluation["integrity"]["manifest_valid"] is False
            # Check error code is present
            assert "manifest_missing" in evaluation["integrity"]["integrity_errors"]
            # Check integrity_error_details also has the error
            detail_codes = [d["code"] for d in evaluation["integrity"]["integrity_error_details"]]
            assert "manifest_missing" in detail_codes

    def test_evaluation_written_when_manifest_missing(self):
        """Test that evaluation.json is STILL WRITTEN when manifest is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create only non-manifest artifacts
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load should NOT raise - returns partial artifacts
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Write evaluation - should succeed even with missing manifest
            output_path = write_evaluation(artifact_dir, evaluation)
            
            # Verify file was written
            assert output_path.exists()
            content = json.loads(output_path.read_text())
            assert content["integrity"]["manifest_valid"] is False

    def test_evaluation_written_when_manifest_invalid_version(self):
        """Test that evaluation.json is STILL WRITTEN when manifest has wrong version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create manifest with wrong version
            manifest = _create_minimal_manifest("run-123")
            manifest["manifest_version"] = "1"  # Wrong version
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Write evaluation - should succeed even with invalid manifest
            output_path = write_evaluation(artifact_dir, evaluation)
            
            # Verify file was written
            assert output_path.exists()
            content = json.loads(output_path.read_text())
            assert content["integrity"]["manifest_valid"] is False
            # Check error code is present (now using codes, not human strings)
            assert "manifest_version_mismatch" in content["integrity"]["integrity_errors"]


class TestStructureMetrics:
    """Test structure metrics extraction."""

    def test_extract_manifest_fields(self):
        """Test that manifest fields are correctly extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            # Create manifest with all fields
            manifest = {
                "manifest_version": "2",
                "run_id": "run-456",
                "created_at": "2024-02-20T12:00:00+00:00",
                "runtime_version": "0.8.2.3",
                "mode": "backtest",
                "correlation_id": "corr-abc",
                "strategy_path": "/path/to/strategy.json",
                "runtime_budgets": {"max_steps": 100},
                "policy_limits": {"max_leverage": 2.0},
                "symbols": ["AAPL", "MSFT"],
            }
            
            decision = _create_minimal_decision("run-456")
            trajectory = _create_minimal_trajectory("run-456")
            deltas = _create_minimal_deltas("run-456")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify structure metrics
            assert evaluation["structure"]["mode"] == "backtest"
            assert evaluation["structure"]["runtime_version"] == "0.8.2.3"
            assert evaluation["structure"]["correlation_id"] == "corr-abc"
            assert evaluation["structure"]["strategy_path"] == "/path/to/strategy.json"
            assert evaluation["structure"]["symbols"] == ["AAPL", "MSFT"]


class TestRunIdMismatch:
    """Test run_id mismatch detection."""

    def test_run_id_mismatch_between_manifest_and_artifact_dir(self):
        """Test that run_id mismatch between manifest and artifact_dir name is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create artifact_dir with a UUID-like name that doesn't match manifest.run_id
            artifact_dir = Path(tmpdir) / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            artifact_dir.mkdir()
            
            # Create manifest with different run_id
            manifest = _create_minimal_manifest("different-run-id")
            decision = _create_minimal_decision("different-run-id")
            trajectory = _create_minimal_trajectory("different-run-id")
            deltas = _create_minimal_deltas("different-run-id")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify run_id_consistent is false
            assert evaluation["integrity"]["run_id_consistent"] is False
            # Check error code is present
            assert "run_id_mismatch" in evaluation["integrity"]["integrity_errors"]
            # Check integrity_error_details also has the error
            detail_codes = [d["code"] for d in evaluation["integrity"]["integrity_error_details"]]
            assert "run_id_mismatch" in detail_codes


class TestConstraintMetrics:
    """Test constraint metrics extraction."""

    def test_runtime_budgets_extraction(self):
        """Test that runtime_budgets are correctly extracted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            manifest = _create_minimal_manifest("run-123")
            manifest["runtime_budgets"] = {
                "max_steps": 50,
                "max_tool_calls": 100,
            }
            manifest["policy_limits"] = {
                "max_leverage": 1.5,
                "max_position_pct": 0.8,
            }
            
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify constraint metrics
            assert evaluation["constraint"]["runtime_budgets"] == {
                "max_steps": 50,
                "max_tool_calls": 100,
            }
            assert evaluation["constraint"]["policy_limits"] == {
                "max_leverage": 1.5,
                "max_position_pct": 0.8,
            }
            assert evaluation["constraint"]["runtime_budget_max_steps"] == 50

    def test_empty_runtime_budgets(self):
        """Test with empty runtime_budgets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)
            
            manifest = _create_minimal_manifest("run-123")
            # runtime_budgets is empty dict
            
            decision = _create_minimal_decision("run-123")
            trajectory = _create_minimal_trajectory("run-123")
            deltas = _create_minimal_deltas("run-123")
            
            (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
            (artifact_dir / "decision.json").write_text(json.dumps(decision))
            (artifact_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (artifact_dir / "deltas.json").write_text(json.dumps(deltas))
            
            # Load and evaluate
            artifacts = load_run_artifacts(artifact_dir)
            evaluation = evaluate_run(artifacts, artifact_dir=artifact_dir)
            
            # Verify constraint metrics
            assert evaluation["constraint"]["runtime_budgets"] == {}
            assert evaluation["constraint"]["runtime_budget_max_steps"] is None
            assert evaluation["constraint"]["truncated_by_budget"] is None
