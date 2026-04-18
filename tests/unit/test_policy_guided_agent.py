"""Unit tests for PolicyGuidedAgent.

These tests verify the policy-guided trading agent:
- Uses evidence policy deterministically
- Falls back to default action when no evidence exists
- Provides explanation output
- Same observation + same policy = same decision
"""

from __future__ import annotations

from services.core.agent import PolicyGuidedAgent
from services.core.policy import DEFAULT_ACTION


class TestPolicyGuidedAgent:
    """Tests for PolicyGuidedAgent class."""

    def test_agent_uses_symbol_preference(self) -> None:
        """Test agent uses symbol-based policy preference."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0, "price": 150.0}

        decision = agent.decide(observation)

        assert decision["type"] == "buy"
        assert decision["source"] == "symbol"
        assert decision["policy_used"] is True

    def test_agent_uses_step_preference(self) -> None:
        """Test agent uses step-based policy preference."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {"0": "sell"},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "UNKNOWN", "step": 0}

        decision = agent.decide(observation)

        assert decision["type"] == "sell"
        assert decision["source"] == "step"
        assert decision["policy_used"] is True

    def test_agent_falls_back_to_default(self) -> None:
        """Test agent falls back to default when no policy match."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "UNKNOWN", "step": 99}

        decision = agent.decide(observation)

        assert decision["type"] == "hold"
        assert decision["source"] == "default"
        assert decision["policy_used"] is False

    def test_agent_symbol_precedence_over_step(self) -> None:
        """Test symbol preference takes precedence over step."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {"0": "sell"},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0}

        decision = agent.decide(observation)

        # Symbol should win
        assert decision["type"] == "buy"
        assert decision["source"] == "symbol"

    def test_explanation_output(self) -> None:
        """Test agent provides explanation for decision."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0}

        explanation = agent.explain_decision(observation)

        assert isinstance(explanation, str)
        assert "AAPL" in explanation
        assert "step 0" in explanation
        assert "buy" in explanation

    def test_deterministic_same_observation_same_decision(self) -> None:
        """Test same observation + same policy = same decision."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 5, "price": 150.0}

        # Make multiple decisions with same observation
        decision1 = agent.decide(observation)
        decision2 = agent.decide(observation)
        decision3 = agent.decide(observation)

        assert decision1 == decision2 == decision3

    def test_hold_action_has_zero_quantity(self) -> None:
        """Test hold action returns qty=0."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0}

        decision = agent.decide(observation)

        assert decision["type"] == "hold"
        assert decision["qty"] == 0

    def test_buy_sell_action_has_quantity_one(self) -> None:
        """Test buy/sell actions return qty=1."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy", "MSFT": "sell"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)

        buy_decision = agent.decide({"symbol": "AAPL", "step": 0})
        sell_decision = agent.decide({"symbol": "MSFT", "step": 0})

        assert buy_decision["type"] == "buy"
        assert buy_decision["qty"] == 1

        assert sell_decision["type"] == "sell"
        assert sell_decision["qty"] == 1

    def test_custom_default_action(self) -> None:
        """Test agent accepts custom default action."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy, default_action="buy")

        # Unknown symbol should use custom default
        decision = agent.decide({"symbol": "UNKNOWN", "step": 0})

        assert decision["type"] == "buy"

    def test_decide_with_reason_combines_results(self) -> None:
        """Test decide_with_reason returns both decision and explanation."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0}

        result = agent.decide_with_reason(observation)

        assert "decision" in result
        assert "explanation" in result
        assert result["decision"]["type"] == "buy"
        assert "AAPL" in result["explanation"]

    def test_agent_properties(self) -> None:
        """Test agent exposes policy and default_action properties."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy, default_action="sell")

        assert agent.policy == policy
        assert agent.default_action == "sell"

    def test_agent_with_empty_policy(self) -> None:
        """Test agent handles empty policy gracefully."""
        policy = {}

        agent = PolicyGuidedAgent(policy)

        # Should fall back to default action
        decision = agent.decide({"symbol": "AAPL", "step": 0})

        assert decision["type"] == DEFAULT_ACTION

    def test_agent_with_context_ignored(self) -> None:
        """Test agent ignores context parameter (for future use)."""
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy"},
            "action_preferences_by_step": {},
        }

        agent = PolicyGuidedAgent(policy)
        observation = {"symbol": "AAPL", "step": 0}
        context = {"some": "context", "ignored": True}

        # Should work without error
        decision = agent.decide(observation, context)

        assert decision["type"] == "buy"


class TestPolicyGuidedAgentIntegration:
    """Integration tests for policy-guided agent with policy module."""

    def test_agent_integration_with_policy_module(self) -> None:
        """Test agent works with evidence policy from policy module."""
        from services.core.policy import apply_evidence_policy

        # Create a policy
        policy = {
            "default_action": "hold",
            "action_preferences_by_symbol": {"AAPL": "buy", "MSFT": "sell"},
            "action_preferences_by_step": {"0": "hold"},
        }

        # Test that policy works with both direct call and agent
        obs1 = {"symbol": "AAPL", "step": 0}
        obs2 = {"symbol": "MSFT", "step": 1}
        obs3 = {"symbol": "GOOG", "step": 0}

        # Direct policy application
        result1 = apply_evidence_policy(obs1, policy)
        result2 = apply_evidence_policy(obs2, policy)
        result3 = apply_evidence_policy(obs3, policy)

        # Agent decision
        agent = PolicyGuidedAgent(policy)
        agent_result1 = agent.decide(obs1)
        agent_result2 = agent.decide(obs2)
        agent_result3 = agent.decide(obs3)

        # Both should agree
        assert result1["action"] == agent_result1["type"]
        assert result2["action"] == agent_result2["type"]
        assert result3["action"] == agent_result3["type"]
