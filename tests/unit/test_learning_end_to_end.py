#!/usr/bin/env python3
"""End-to-end test for the full learning loop scaffold.

This test validates the complete learning loop:
1. Select valid runs from fixture experiment
2. Export dataset to JSONL
3. Replay dataset
4. Run stub learner
5. Assert expected results

Uses: tests/fixtures/learning_experiment/
"""

import json
import sys
from pathlib import Path

import pytest

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.core.learning import (
    export_learning_dataset,
    iter_trajectory_steps,
    run_stub_learner,
    select_learning_runs,
)

# Path to fixture experiment
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "learning_experiment"


class TestLearningEndToEnd:
    """Test the complete learning loop end-to-end."""

    def test_full_learning_loop(self, tmp_path):
        """Test the full learning loop with fixture data."""
        # Verify fixture exists
        assert FIXTURE_DIR.exists(), f"Fixture not found: {FIXTURE_DIR}"
        assert (FIXTURE_DIR / "evaluation_summary.json").exists()

        # STEP 1: Select learning runs
        selected_runs = select_learning_runs(
            FIXTURE_DIR,
            require_valid=True,
            include_truncated=True,
        )

        # Should have 2 valid runs from fixture
        assert len(selected_runs) == 2, f"Expected 2 runs, got {len(selected_runs)}"
        assert selected_runs[0]["run_id"] == "run-001"
        assert selected_runs[1]["run_id"] == "run-002"

        # STEP 2: Export learning dataset
        dataset_path = tmp_path / "test_trajectories.jsonl"

        result_path = export_learning_dataset(
            FIXTURE_DIR,
            dataset_path,
            require_valid=True,
        )

        # Verify dataset was created
        assert result_path.exists(), "Dataset file not created"

        # Count rows - should have 8 rows (5 from run-001 + 3 from run-002)
        row_count = 0
        with open(result_path) as f:
            for line in f:
                if line.strip():
                    row_count += 1

        assert row_count > 0, "No rows exported"
        assert row_count == 8, f"Expected 8 rows, got {row_count}"

        # STEP 3: Replay dataset
        replayed_trajectories = list(iter_trajectory_steps(result_path))

        assert len(replayed_trajectories) == 8, f"Expected 8 trajectories, got {len(replayed_trajectories)}"

        # Verify trajectory structure
        for traj in replayed_trajectories:
            assert "run_id" in traj
            assert "step_index" in traj
            assert "observation" in traj
            assert "action" in traj
            assert "done" in traj

        # STEP 4: Run stub learner
        report_path = tmp_path / "test_report.json"

        run_stub_learner(result_path, report_path)

        # Verify report was created
        assert report_path.exists(), "Report file not created"

        # Load and verify report
        with open(report_path) as f:
            report = json.load(f)

        # Assert expected values
        assert report["total_runs"] == 2, f"Expected 2 runs, got {report['total_runs']}"
        assert report["total_steps"] == 8, f"Expected 8 steps, got {report['total_steps']}"
        assert report["average_steps_per_run"] == 4.0, f"Expected 4.0 avg, got {report['average_steps_per_run']}"

        # Verify action counts
        action_counts = report["action_counts"]
        assert action_counts["hold"] == 4, f"Expected 4 holds, got {action_counts.get('hold')}"
        assert action_counts["buy"] == 2, f"Expected 2 buys, got {action_counts.get('buy')}"
        assert action_counts["sell"] == 2, f"Expected 2 sells, got {action_counts.get('sell')}"

        # Verify symbol counts
        symbol_counts = report["symbol_counts"]
        assert "AAPL" in symbol_counts
        assert "MSFT" in symbol_counts

        print("✅ Full learning loop test passed!")
        print(f"   - Selected runs: {len(selected_runs)}")
        print(f"   - Exported rows: {row_count}")
        print(f"   - Report: total_runs={report['total_runs']}, total_steps={report['total_steps']}")

    def test_learning_loop_with_invalid_runs_filtered(self, tmp_path):
        """Test that invalid runs are filtered when require_valid=True."""
        # Create a temp experiment with invalid runs
        temp_experiment = tmp_path / "temp_experiment"
        temp_experiment.mkdir()
        artifacts_dir = temp_experiment / "artifacts"
        artifacts_dir.mkdir()

        # Create evaluation_summary with mixed valid/invalid
        evaluation = {
            "aggregate": {"total_runs": 3},
            "runs": [
                {"run_id": "run-001", "manifest_valid": True, "integrity_errors": [], "steps_executed": 3},
                {"run_id": "run-002", "manifest_valid": False, "integrity_errors": ["missing_manifest"], "steps_executed": 3},
                {"run_id": "run-003", "manifest_valid": True, "integrity_errors": [], "steps_executed": 3},
            ],
            "summary": {"total_runs": 3, "ok_runs": 2, "failed_runs": 1},
        }

        (temp_experiment / "evaluation_summary.json").write_text(json.dumps(evaluation))

        # Create artifacts for valid runs only
        for run_id in ["run-001", "run-003"]:
            run_dir = artifacts_dir / run_id
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps({"run_id": run_id}))
            trajectory = [
                {"observation": {"step": 0}, "action": {"type": "hold"}, "done": False},
            ]
            (run_dir / "trajectory.json").write_text(json.dumps(trajectory))
            (run_dir / "decision.json").write_text(json.dumps({"run_id": run_id}))
            (run_dir / "deltas.json").write_text(json.dumps({"run_id": run_id, "deltas": []}))

        # Select only valid runs
        selected_runs = select_learning_runs(
            temp_experiment,
            require_valid=True,
            include_truncated=True,
        )

        # Should only get run-001 and run-003 (run-002 has invalid manifest)
        assert len(selected_runs) == 2
        run_ids = [r["run_id"] for r in selected_runs]
        assert "run-001" in run_ids
        assert "run-003" in run_ids
        assert "run-002" not in run_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
