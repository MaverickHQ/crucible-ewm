"""Policy-Guided Trading Agent.

A minimal agent that consumes an evidence policy and uses it to make
trading decisions in the market-path environment.

This is NOT RL training - it's a deterministic policy-guided agent that
demonstrates how experiment evidence can influence future decisions.

Purpose:
- Show how an agent consults an evidence policy for trading decisions
- Provide deterministic action selection based on policy preferences
- Demonstrate the final link in the learning loop: evidence -> decision

Example usage:
    from ewm_core.agent import PolicyGuidedAgent
    from ewm_core.policy import load_evidence_policy

    policy = load_evidence_policy("outputs/learning/evidence_policy.json")
    agent = PolicyGuidedAgent(policy)

    observation = {"symbol": "AAPL", "step": 0, "price": 150.0}
    decision = agent.decide(observation)
    explanation = agent.explain_decision(observation)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ewm_core.policy import DEFAULT_ACTION, apply_evidence_policy


class PolicyGuidedAgent:
    """
    A minimal policy-guided trading agent.

    This agent consumes an evidence policy and uses it to make deterministic
    trading decisions based on market observations.

    The agent:
    - Consults the evidence policy for symbol/step action preferences
    - Chooses actions deterministically using the policy
    - Falls back to default_action if no specific evidence exists
    - Provides explanations for each decision

    This is NOT:
    - RL training with reward optimization
    - Policy gradient learning
    - Stochastic decision making

    This IS:
    - Deterministic action selection
    - Evidence-based decision making
    - The final link: experiment evidence -> future decisions
    """

    def __init__(
        self,
        policy: Dict[str, Any],
        default_action: str = DEFAULT_ACTION,
    ):
        """
        Initialize the policy-guided agent.

        Args:
            policy: Evidence policy dictionary containing:
                - default_action: Fallback action when no preference matches
                - action_preferences_by_symbol: Preferred action per symbol
                - action_preferences_by_step: Preferred action per step position
            default_action: Fallback action (defaults to policy default or "hold")
        """
        self._policy = dict(policy)
        self._default_action = default_action or policy.get("default_action", DEFAULT_ACTION)

    @property
    def policy(self) -> Dict[str, Any]:
        """Return a copy of the evidence policy."""
        return dict(self._policy)

    @property
    def default_action(self) -> str:
        """Return the default action."""
        return self._default_action

    def decide(
        self,
        observation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a trading decision based on observation and evidence policy.

        This method uses the evidence policy to determine what action
        should be taken based on the current market observation.

        Decision logic (in order of precedence):
        1. If symbol exists in action_preferences_by_symbol, use that action
        2. If step_position exists in action_preferences_by_step, use that action
        3. Fall back to agent's default_action (not policy's)

        Args:
            observation: Current market observation containing:
                - symbol: The trading symbol (e.g., "AAPL")
                - step: Current step position (or step_index)
                - price: Current price (optional)
                - Other market data
            context: Optional additional context (ignored, for future use)

        Returns:
            Dictionary containing the decision:
            - type: Action type ("hold", "buy", "sell")
            - symbol: Symbol from observation (if any)
            - qty: Quantity (default 1 for buy/sell, 0 for hold)
            - source: Where decision came from ("symbol", "step", "default")
            - policy_used: Whether policy influenced the decision
            - policy: Reference to the policy used

        Example:
            >>> agent = PolicyGuidedAgent(policy)
            >>> obs = {"symbol": "AAPL", "step": 0, "price": 150.0}
            >>> decision = agent.decide(obs)
            >>> print(decision)
            {"type": "hold", "symbol": "AAPL", "qty": 0, "source": "symbol", "policy_used": True}
        """
        # Apply the evidence policy to get the base decision
        policy_decision = apply_evidence_policy(observation, self._policy)

        # Use agent's custom default, not the policy's default
        # This ensures custom default_action parameter is respected
        if policy_decision.get("source") == "default":
            action_type = self._default_action
        else:
            action_type = policy_decision.get("action", self._default_action)
        
        source = policy_decision.get("source", "default")
        policy_used = policy_decision.get("policy_used", False)
        
        # Override source for clarity when using agent's custom default
        if source == "default" and policy_decision.get("action") != self._default_action:
            # Policy had a default but agent has custom default - use agent's
            source = "agent_default"
            policy_used = False

        # Extract symbol from observation
        symbol = observation.get("symbol", "")

        # Determine quantity based on action type
        if action_type == "hold":
            qty = 0
        else:
            qty = 1  # Default quantity for buy/sell

        # Build the decision dict
        decision: Dict[str, Any] = {
            "type": action_type,
            "symbol": symbol,
            "qty": qty,
            "source": source,
            "policy_used": policy_used,
        }

        # Include observation summary for traceability
        if "price" in observation:
            decision["price"] = observation["price"]

        if "step" in observation:
            decision["step"] = observation["step"]
        elif "step_index" in observation:
            decision["step"] = observation["step_index"]

        return decision

    def explain_decision(self, observation: Dict[str, Any]) -> str:
        """
        Provide a human-readable explanation of why a decision was made.

        This method explains how the evidence policy influenced the decision
        based on the current observation.

        Args:
            observation: Current market observation

        Returns:
            String explaining the decision rationale

        Example:
            >>> agent = PolicyGuidedAgent(policy)
            >>> obs = {"symbol": "AAPL", "step": 0}
            >>> explanation = agent.explain_decision(obs)
            >>> print(explanation)
            "Decision for AAPL at step 0: hold (policy preference for symbol)"
        """
        # Get the decision
        decision = self.decide(observation)

        # Extract key info
        symbol = observation.get("symbol", "unknown")
        step = observation.get("step", observation.get("step_index", "?"))
        action = decision.get("type", "hold")
        source = decision.get("source", "default")
        policy_used = decision.get("policy_used", False)

        # Build explanation
        if policy_used:
            if source == "symbol":
                reason = f"policy preference for symbol '{symbol}'"
            elif source == "step":
                reason = f"policy preference for step position {step}"
            else:
                reason = "policy preference"
        else:
            reason = "no policy match, using default"

        explanation = f"Decision for {symbol} at step {step}: {action} ({reason})"

        return explanation

    def decide_with_reason(
        self,
        observation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a decision and include the explanation in the result.

        This is a convenience method that combines decide() and explain_decision()
        into a single call.

        Args:
            observation: Current market observation
            context: Optional additional context

        Returns:
            Dictionary containing decision and explanation:
            - decision: The action decision
            - explanation: Human-readable explanation

        Example:
            >>> result = agent.decide_with_reason({"symbol": "AAPL", "step": 0})
            >>> print(result["explanation"])
            "Decision for AAPL at step 0: hold (policy preference for symbol)"
        """
        decision = self.decide(observation, context)
        explanation = self.explain_decision(observation)

        return {
            "decision": decision,
            "explanation": explanation,
        }
