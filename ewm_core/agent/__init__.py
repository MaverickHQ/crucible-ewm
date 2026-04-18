"""Agent module for Executable World Models.

This module provides agent implementations that can consume evidence policies
to make deterministic trading decisions.

This is NOT RL training - it's a deterministic policy-guided agent.
"""

from .policy_guided_agent import PolicyGuidedAgent

__all__ = ["PolicyGuidedAgent"]
