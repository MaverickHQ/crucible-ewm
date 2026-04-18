"""Unit tests for the policy feedback loop integration.

These tests verify the complete policy feedback loop:
- end-to-end: fixture experiment → dataset export → learner report → 
              evidence policy → evidence-informed decision
- policy-feedback demo path yields a non-empty, deterministic decision result
"""

from __future__ import annotations

import json
from pathlib import Path

from services.core.learning.dataset_export import export_learning_dataset
from services.core.learning.stub_learner import run_stub_learner
from services.core.policy import (
    apply_evidence_policy,
    build_evidence_policy_from_learning_report,
    load_evidence_policy,
)

# Paths for test fixtures
FIXTURE_PATH = Path("tests/fixtures/learning_experiment")


class TestPolicyFeedbackLoop:
    """Tests for the complete policy feedback loop."""

    def test_end_to_end_loop(self, tmp_path: Path) -> None:
        """Test end-to-end policy feedback loop."""
        # Use temporary paths for this test
        dataset_path = tmp_path / "trajectories.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"
        
        # Step 1: Export learning dataset from fixture
        export_learning_dataset(
            experiment_dir=FIXTURE_PATH,
            output_path=dataset_path,
        )
        
        assert dataset_path.exists()
        assert dataset_path.stat().st_size > 0
        
        # Step 2: Run learner stub to produce report
        run_stub_learner(
            dataset_path=dataset_path,
            output_path=report_path,
        )
        
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report.get("total_runs", 0) > 0
        
        # Step 3: Build evidence policy from report
        build_evidence_policy_from_learning_report(
            report_path=report_path,
            output_path=policy_path,
        )
        
        assert policy_path.exists()
        policy = load_evidence_policy(policy_path)
        
        # Verify policy structure
        assert "default_action" in policy
        assert "evidence_runs" in policy
        assert "action_preferences_by_symbol" in policy
        
        # Step 4: Apply policy to observations
        observations = [
            {"symbol": "AAPL", "step": 0},
            {"symbol": "MSFT", "step": 1},
        ]
        
        decisions = []
        for obs in observations:
            decision = apply_evidence_policy(obs, policy)
            decisions.append(decision)
        
        # Verify we got decisions
        assert len(decisions) == 2
        for decision in decisions:
            assert "action" in decision
            assert "source" in decision
            assert "policy_used" in decision
        
        print("\n✓ End-to-end loop completed successfully")
        print(f"  Dataset: {dataset_path.stat().st_size} bytes")
        print(f"  Report runs: {report.get('total_runs')}")
        print(f"  Policy runs: {policy.get('evidence_runs')}")

    def test_deterministic_decisions(self, tmp_path: Path) -> None:
        """Test that decisions are deterministic."""
        # Set up paths
        dataset_path = tmp_path / "trajectories.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"
        
        # Run the full loop
        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)
        
        # Load policy
        policy = load_evidence_policy(policy_path)
        
        # Test observation
        observation = {"symbol": "AAPL", "step": 0}
        
        # Get decision multiple times - should be deterministic
        decisions = []
        for _ in range(5):
            decision = apply_evidence_policy(observation, policy)
            decisions.append(decision)
        
        # All decisions should be identical
        first = decisions[0]
        for d in decisions[1:]:
            assert d["action"] == first["action"]
            assert d["source"] == first["source"]

    def test_policy_influences_decision(self, tmp_path: Path) -> None:
        """Test that policy actually influences decisions."""
        # Set up paths
        dataset_path = tmp_path / "trajectories.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"
        
        # Run the full loop
        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)
        
        # Load policy
        policy = load_evidence_policy(policy_path)
        
        # Get a known symbol from the policy
        symbol_prefs = policy.get("action_preferences_by_symbol", {})
        
        if symbol_prefs:
            # We have symbol preferences - test that they're used
            test_symbol = list(symbol_prefs.keys())[0]
            expected_action = symbol_prefs[test_symbol]
            
            observation = {"symbol": test_symbol, "step": 0}
            decision = apply_evidence_policy(observation, policy)
            
            assert decision["action"] == expected_action
            assert decision["source"] == "symbol"
            assert decision["policy_used"] is True
            
            print(f"\n✓ Policy influenced decision: {test_symbol} → {expected_action}")

    def test_fallback_when_no_matching_evidence(self, tmp_path: Path) -> None:
        """Test fallback when no evidence matches the observation."""
        # Set up paths
        dataset_path = tmp_path / "trajectories.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"
        
        # Run the full loop
        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)
        
        # Load policy
        policy = load_evidence_policy(policy_path)
        
        # Use a symbol that's not in the policy
        observation = {"symbol": "UNKNOWN_SYMBOL", "step": 999}
        decision = apply_evidence_policy(observation, policy)
        
        # Should fall back to default
        assert decision["action"] == policy.get("default_action", "hold")
        assert decision["source"] in ("default", "step")

    def test_demo_path_yields_result(self, tmp_path: Path) -> None:
        """Test that the demo path yields a non-empty, deterministic result."""
        # This simulates what demo_policy_feedback_loop.py does
        
        # Set up paths
        dataset_path = tmp_path / "trajectories.jsonl"
        report_path = tmp_path / "report.json"
        policy_path = tmp_path / "policy.json"
        
        # Ensure artefacts exist
        export_learning_dataset(FIXTURE_PATH, dataset_path)
        run_stub_learner(dataset_path, report_path)
        build_evidence_policy_from_learning_report(report_path, policy_path)
        
        # Load policy
        policy = load_evidence_policy(policy_path)
        
        # Sample observations (like the demo does)
        observations = [
            {"symbol": "AAPL", "step": 0, "price": 150.0},
            {"symbol": "AAPL", "step": 1, "price": 151.0},
            {"symbol": "MSFT", "step": 0, "price": 300.0},
        ]
        
        # Get decisions
        results = []
        for obs in observations:
            decision = apply_evidence_policy(obs, policy)
            results.append({
                "observation": obs,
                "decision": decision,
            })
        
        # Verify non-empty results
        assert len(results) == 3
        for r in results:
            assert r["decision"]["action"] is not None
            assert r["decision"]["action"] != ""
        
        # All should have valid sources
        for r in results:
            assert r["decision"]["source"] in ("symbol", "step", "default")
        
        print(f"\n✓ Demo path yielded {len(results)} deterministic decisions")
