"""Unit tests for evidence_policy module.

These tests verify the deterministic policy feedback functionality:
- load_evidence_policy reads expected JSON structure
- build_evidence_policy_from_learning_report produces deterministic policy JSON
- apply_evidence_policy returns deterministic decision output
- missing symbol / missing step falls back to default_action
- same report input produces identical policy output
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.core.policy import (
    DEFAULT_ACTION,
    apply_evidence_policy,
    build_evidence_policy_from_learning_report,
    get_baseline_decision,
    load_evidence_policy,
    write_evidence_policy,
)


class TestLoadEvidencePolicy:
    """Tests for load_evidence_policy function."""

    def test_load_existing_policy(self, tmp_path: Path) -> None:
        """Test loading a valid policy file."""
        policy_data = {
            "environment_type": "trading",
            "generated_from": "test_report.json",
            "evidence_runs": 2,
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "hold", "MSFT": "buy"},
            "action_preferences_by_step": {"0": "hold", "1": "buy"},
        }
        
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(policy_data, sort_keys=True))
        
        loaded = load_evidence_policy(policy_file)
        
        assert loaded["environment_type"] == "trading"
        assert loaded["evidence_runs"] == 2
        assert loaded["default_action"] == "hold"
        assert loaded["action_preferences_by_symbol"]["AAPL"] == "hold"

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_evidence_policy(tmp_path / "nonexistent.json")


class TestWriteEvidencePolicy:
    """Tests for write_evidence_policy function."""

    def test_write_policy_file(self, tmp_path: Path) -> None:
        """Test writing a policy to file."""
        policy_data = {
            "environment_type": "trading",
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {},
        }
        
        output_path = tmp_path / "output_policy.json"
        result = write_evidence_policy(policy_data, output_path)
        
        assert result.exists()
        loaded = json.loads(result.read_text())
        assert loaded["environment_type"] == "trading"

    def test_deterministic_output(self, tmp_path: Path) -> None:
        """Test that output is deterministic (sorted keys)."""
        policy_data = {
            "z_key": "z_value",
            "a_key": "a_value",
            "m_key": "m_value",
        }
        
        output_path = tmp_path / "deterministic.json"
        write_evidence_policy(policy_data, output_path)
        
        content = output_path.read_text()
        # Keys should be sorted
        assert content.index("a_key") < content.index("m_key")
        assert content.index("m_key") < content.index("z_key")


class TestBuildEvidencePolicy:
    """Tests for build_evidence_policy_from_learning_report function."""

    def test_build_from_learning_report(self, tmp_path: Path) -> None:
        """Test building policy from a learning report."""
        # Create a minimal learning report
        report_data = {
            "total_runs": 3,
            "heuristics": {
                "most_common_action": {"type": "hold", "count": 10},
                "most_common_action_by_symbol": {
                    "AAPL": {"action": "buy", "count": 5},
                    "MSFT": {"action": "sell", "count": 3},
                },
                "step_position_actions": {
                    "0": {"action": "hold", "count": 2},
                    "1": {"action": "buy", "count": 3},
                },
            },
        }
        
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(report_data, sort_keys=True))
        
        output_path = tmp_path / "policy.json"
        result = build_evidence_policy_from_learning_report(report_path, output_path)
        
        assert result.exists()
        
        policy = json.loads(result.read_text())
        assert policy["evidence_runs"] == 3
        assert policy["default_action"] == "hold"
        assert policy["action_preferences_by_symbol"]["AAPL"] == "buy"
        assert policy["action_preferences_by_symbol"]["MSFT"] == "sell"
        assert policy["action_preferences_by_step"]["0"] == "hold"
        assert policy["action_preferences_by_step"]["1"] == "buy"

    def test_build_with_no_heuristics(self, tmp_path: Path) -> None:
        """Test building policy with empty heuristics."""
        report_data = {
            "total_runs": 0,
            "heuristics": {},
        }
        
        report_path = tmp_path / "empty_report.json"
        report_path.write_text(json.dumps(report_data, sort_keys=True))
        
        output_path = tmp_path / "policy.json"
        build_evidence_policy_from_learning_report(report_path, output_path)
        
        policy = json.loads(output_path.read_text())
        # Should fall back to default action
        assert policy["default_action"] == DEFAULT_ACTION

    def test_same_report_produces_identical_policy(self, tmp_path: Path) -> None:
        """Test that same report always produces identical policy (deterministic)."""
        report_data = {
            "total_runs": 2,
            "heuristics": {
                "most_common_action": {"type": "buy", "count": 5},
                "most_common_action_by_symbol": {"AAPL": {"action": "buy", "count": 3}},
                "step_position_actions": {"0": {"action": "hold", "count": 2}},
            },
        }
        
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(report_data, sort_keys=True))
        
        # Build policy twice
        output1 = tmp_path / "policy1.json"
        output2 = tmp_path / "policy2.json"
        
        build_evidence_policy_from_learning_report(report_path, output1)
        build_evidence_policy_from_learning_report(report_path, output2)
        
        # Should be identical
        assert output1.read_text() == output2.read_text()


class TestApplyEvidencePolicy:
    """Tests for apply_evidence_policy function."""

    def test_apply_with_symbol_preference(self) -> None:
        """Test applying policy with symbol-based preference."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }
        
        observation = {"symbol": "AAPL", "step": 5}
        decision = apply_evidence_policy(observation, policy)
        
        assert decision["action"] == "buy"
        assert decision["source"] == "symbol"
        assert decision["policy_used"] is True

    def test_apply_with_step_preference(self) -> None:
        """Test applying policy with step-based preference."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {"1": "sell"},
        }
        
        observation = {"symbol": "UNKNOWN", "step": 1}
        decision = apply_evidence_policy(observation, policy)
        
        assert decision["action"] == "sell"
        assert decision["source"] == "step"
        assert decision["policy_used"] is True

    def test_fallback_to_default_action(self) -> None:
        """Test fallback to default action when no preference matches."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {},
        }
        
        observation = {"symbol": "UNKNOWN", "step": 99}
        decision = apply_evidence_policy(observation, policy)
        
        assert decision["action"] == "hold"
        assert decision["source"] == "default"
        assert decision["policy_used"] is False

    def test_symbol_takes_precedence_over_step(self) -> None:
        """Test that symbol preference takes precedence over step preference."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {"0": "sell"},
        }
        
        observation = {"symbol": "AAPL", "step": 0}
        decision = apply_evidence_policy(observation, policy)
        
        # Symbol should take precedence
        assert decision["action"] == "buy"
        assert decision["source"] == "symbol"


class TestGetBaselineDecision:
    """Tests for get_baseline_decision function."""

    def test_baseline_returns_hold(self) -> None:
        """Test that baseline always returns hold."""
        observation = {"symbol": "AAPL", "step": 0}
        decision = get_baseline_decision(observation)
        
        assert decision["action"] == "hold"
        assert decision["source"] == "baseline"
        assert decision["policy_used"] is False

    def test_baseline_ignores_observation(self) -> None:
        """Test that baseline ignores observation content."""
        observation = {"symbol": "ANY", "step": 999, "price": 9999.0}
        decision = get_baseline_decision(observation)
        
        assert decision["action"] == "hold"
