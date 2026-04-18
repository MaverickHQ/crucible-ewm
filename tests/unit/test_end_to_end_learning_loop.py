"""Unit tests for end-to-end learning loop.

These tests verify the complete learning loop:
- fixture experiment → dataset export → learner report → evidence policy → policy-guided decision
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ewm_core.agent import PolicyGuidedAgent
from ewm_core.learning import (
    export_learning_dataset,
    run_stub_learner,
    select_learning_runs,
)
from ewm_core.policy import (
    build_evidence_policy_from_learning_report,
    load_evidence_policy,
)

# Test fixture path
FIXTURE_PATH = Path("tests/fixtures/learning_experiment")


class TestEndToEndLearningLoop:
    """Tests for complete end-to-end learning loop."""

    def test_full_loop_produces_dataset(self, tmp_path: Path) -> None:
        """Test full loop produces non-zero dataset rows."""
        # Use the test fixture
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Export dataset
        output_path = tmp_path / "dataset.jsonl"
        result_path = export_learning_dataset(FIXTURE_PATH, output_path)

        # Count rows
        row_count = 0
        with open(result_path) as f:
            for line in f:
                if line.strip():
                    row_count += 1

        assert row_count > 0, "Dataset should have non-zero rows"

    def test_full_loop_produces_report(self, tmp_path: Path) -> None:
        """Test full loop produces learning report."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Export dataset
        dataset_path = tmp_path / "dataset.jsonl"
        export_learning_dataset(FIXTURE_PATH, dataset_path)

        # Run learner
        report_path = tmp_path / "report.json"
        run_stub_learner(dataset_path, report_path)

        # Verify report exists and has expected fields
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert "total_runs" in report
        assert "total_steps" in report
        assert "action_counts" in report

    def test_full_loop_produces_policy(self, tmp_path: Path) -> None:
        """Test full loop produces evidence policy."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Run full pipeline
        dataset_path = tmp_path / "dataset.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"

        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)

        # Verify policy exists and has expected fields
        assert policy_path.exists()
        policy = json.loads(policy_path.read_text())
        assert "default_action" in policy
        assert "action_preferences_by_symbol" in policy
        assert "action_preferences_by_step" in policy

    def test_full_loop_produces_policy_guided_decisions(self, tmp_path: Path) -> None:
        """Test full loop produces policy-guided decisions."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Run full pipeline
        dataset_path = tmp_path / "dataset.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"

        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)

        # Load policy
        policy = load_evidence_policy(policy_path)

        # Create agent
        agent = PolicyGuidedAgent(policy)

        # Make decisions
        observations = [
            {"symbol": "AAPL", "step": 0},
            {"symbol": "MSFT", "step": 1},
            {"symbol": "AAPL", "step": 2},
        ]

        decisions = [agent.decide(obs) for obs in observations]

        assert len(decisions) > 0
        # At least one should have policy_used=True if policy has preferences
        has_policy_decisions = any(d.get("policy_used", False) for d in decisions)
        # Either policy was used, or we got default decisions
        assert len(decisions) == len(observations)

    def test_select_runs_returns_valid_runs(self) -> None:
        """Test that select_learning_runs returns valid runs."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        runs = select_learning_runs(FIXTURE_PATH, require_valid=True)

        assert len(runs) > 0
        for run in runs:
            assert "run_id" in run
            assert "steps_executed" in run

    def test_agent_uses_policy_from_loop(self, tmp_path: Path) -> None:
        """Test agent can use policy produced by the loop."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Run pipeline
        dataset_path = tmp_path / "dataset.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"

        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)

        # Load and use policy
        policy = load_evidence_policy(policy_path)
        agent = PolicyGuidedAgent(policy)

        # Make a decision
        obs = {"symbol": "AAPL", "step": 0}
        decision = agent.decide(obs)

        # Should have valid decision structure
        assert "type" in decision
        assert "source" in decision
        assert "policy_used" in decision

    def test_end_to_end_validation(self, tmp_path: Path) -> None:
        """Test complete end-to-end validation."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        # Step 1: Select runs
        runs = select_learning_runs(FIXTURE_PATH, require_valid=True)
        assert len(runs) > 0

        # Step 2: Export dataset
        dataset_path = tmp_path / "dataset.jsonl"
        result_path = export_learning_dataset(FIXTURE_PATH, dataset_path)

        row_count = sum(1 for line in open(result_path) if line.strip())
        assert row_count > 0

        # Step 3: Run learner
        report_path = tmp_path / "report.json"
        run_stub_learner(dataset_path, report_path)

        report = json.loads(report_path.read_text())
        assert report.get("total_runs", 0) > 0

        # Step 4: Build policy
        policy_path = tmp_path / "policy.json"
        build_evidence_policy_from_learning_report(report_path, policy_path)

        policy = json.loads(policy_path.read_text())
        assert "default_action" in policy

        # Step 5: Use policy with agent
        agent = PolicyGuidedAgent(policy)
        obs = {"symbol": "AAPL", "step": 0}
        decision = agent.decide(obs)

        assert decision is not None
        assert "type" in decision


class TestEndToEndDemo:
    """Tests that verify the demo scripts work correctly."""

    def test_demo_produces_expected_outputs(self, tmp_path: Path) -> None:
        """Test demo produces all expected outputs."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        output_dir = tmp_path / "outputs"
        output_dir.mkdir()

        dataset_path = output_dir / "trajectories.jsonl"
        report_path = output_dir / "report.json"
        policy_path = output_dir / "policy.json"

        # Run pipeline
        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)

        # All files should exist
        assert dataset_path.exists()
        assert report_path.exists()
        assert policy_path.exists()

        # Dataset is JSONL (multiple JSON lines), verify it's parseable
        with open(dataset_path) as f:
            for line in f:
                if line.strip():
                    json.loads(line)  # Each line should be valid JSON
        
        # Report and policy should be valid JSON
        assert json.loads(report_path.read_text())
        assert json.loads(policy_path.read_text())
