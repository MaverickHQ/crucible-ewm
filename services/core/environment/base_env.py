"""
Base Environment Interface

This module defines a minimal abstract environment interface for stateful 
deterministic experiments. It provides a lightweight interface for building
agent experiments that require stateful world interactions.

This is NOT:
- A market simulator with order matching
- A broker with slippage modeling
- An RL trainer with reward optimization
- A world model implementation

This IS:
- A stateful world interface for replaying market paths
- A simple, typed interface for deterministic stateful experiments
- Compatible with the existing trading/market-path framing
- Designed to support future environment-based work (e.g., Essay 8 "Agents Need Worlds")

The primary concrete implementation is MarketPathEnvironment (also available as 
TradingEnvironment for backwards compatibility), which provides deterministic 
market-path replay where actions may be recorded/echoed but are not financially executed.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseEnvironment(ABC):
    """
    Abstract base class for deterministic stateful environments.
    
    This provides a minimal interface for stateful agent experiments
    where the environment state evolves deterministically based on
    agent actions.
    
    All implementations should:
    - Return plain dicts (no external library types)
    - Be fully deterministic given the same inputs
    - Not introduce async behavior
    - Keep state transitions simple and inspectable
    """
    
    @abstractmethod
    def reset(self) -> dict[str, Any]:
        """
        Reset the environment to its initial state.
        
        Returns:
            dict: The initial observation/state after reset.
        """
        pass
    
    @abstractmethod
    def state(self) -> dict[str, Any]:
        """
        Get the current environment state.
        
        Returns:
            dict: Current state including observation, done flag, step index, etc.
        """
        pass
    
    @abstractmethod
    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one step in the environment given an action.
        
        Args:
            action: A dictionary representing the action to take.
            
        Returns:
            dict: A dictionary containing:
                - observation: The observation after the step
                - done: Boolean indicating if episode is complete
                - step_index: Current step index
                - applied_action: The action that was applied
                - info: Additional debug/info dict
        """
        pass
