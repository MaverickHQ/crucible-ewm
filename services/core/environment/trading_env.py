"""
MarketPathEnvironment (formerly TradingEnvironment)

A deterministic, stateful environment that replays a market path 
and allows an agent to interact with it via step actions.

This is NOT:
- A market simulator with order matching
- A broker with slippage modeling
- An RL trainer with reward optimization
- A world model implementation

This IS:
- A stateful world interface for replaying market paths
- A deterministic market path replay environment
- A lightweight deterministic environment (not a market simulator)
- Designed to support future environment-based work (Essay 8 "Agents Need Worlds")

Actions may be recorded/echoed but are NOT financially executed. 
No PnL is computed, no orders are matched, no rewards are calculated.

Example:
    >>> path = [{"AAPL": 100.0}, {"AAPL": 101.0}, {"AAPL": 102.0}]
    >>> env = MarketPathEnvironment(market_path=path, initial_cash=10000.0)
    >>> env.reset()
    >>> env.step({"type": "hold"})
"""

from typing import Any

from .base_env import BaseEnvironment


class TradingEnvironment(BaseEnvironment):
    """
    A deterministic trading environment that replays a market path.
    
    This environment maintains state across steps, allowing an agent to
    interact with a sequential market observation path. It is designed
    to be a lightweight abstraction for stateful market-path experiments.
    
    The environment:
    - Advances through a fixed sequence of market observations
    - Records (but does not execute) agent actions
    - Does NOT compute rewards, PnL, or handle order execution
    - Is fully deterministic given the same inputs
    """
    
    def __init__(
        self,
        market_path: list[dict[str, float]],
        initial_cash: float = 10_000.0,
        initial_positions: dict[str, int] | None = None,
    ):
        """
        Initialize the trading environment.
        
        Args:
            market_path: List of market observations (dicts mapping symbol to price).
                        Each step represents one timestep in the market.
            initial_cash: Initial cash balance (default: 10,000.0).
            initial_positions: Initial positions as dict of symbol -> quantity.
                              Defaults to empty positions if not provided.
        """
        if not market_path:
            raise ValueError("market_path must contain at least one step")
        
        self._market_path = market_path
        self._num_steps = len(market_path)
        self._initial_cash = initial_cash
        self._initial_positions = initial_positions or {}
        
        # Internal state
        self._current_step = 0
        self._cash = initial_cash
        self._positions = dict(self._initial_positions)
        self._done = False
        self._action_history: list[dict[str, Any]] = []
    
    def reset(self) -> dict[str, Any]:
        """
        Reset the environment to its initial state.
        
        Returns:
            dict: Initial observation/state containing:
                - current_step: 0
                - done: False
                - observation: First market observation
                - cash_balance: Initial cash
                - positions: Initial positions
        """
        self._current_step = 0
        self._cash = self._initial_cash
        self._positions = dict(self._initial_positions)
        self._done = False
        self._action_history = []
        
        return self._build_observation()
    
    def state(self) -> dict[str, Any]:
        """
        Get the current environment state.
        
        Returns:
            dict: Current state containing:
                - current_step: Current step index
                - done: Whether episode is complete
                - observation: Current market observation
                - cash_balance: Current cash balance
                - positions: Current positions
        """
        return self._build_state()
    
    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one step in the environment.
        
        The environment advances one market step and records the action.
        No actual trade execution, reward computation, or PnL is performed.
        
        Args:
            action: A dict representing the action, e.g.:
                - {"type": "hold"}
                - {"type": "observe"}
                - {"type": "buy", "symbol": "AAPL", "qty": 1}
                
        Returns:
            dict: Step result containing:
                - observation: Market observation at new step
                - done: Whether episode is now complete
                - step_index: Current step index
                - applied_action: The action that was applied
                - info: Additional info (action_history, etc.)
        """
        if self._done:
            return {
                "observation": {},
                "done": True,
                "step_index": self._current_step,
                "applied_action": action,
                "info": {"error": "Episode already complete, call reset()"}
            }
        
        # Record the action (deterministic, no execution)
        self._action_history.append(dict(action))
        
        # Advance to next step
        self._current_step += 1
        
        # Check if we've reached the end
        if self._current_step >= self._num_steps:
            self._done = True
        
        return {
            "observation": self._build_observation()["observation"],
            "done": self._done,
            "step_index": self._current_step,
            "applied_action": dict(action),
            "info": {
                "action_history": list(self._action_history),
            }
        }
    
    def _build_observation(self) -> dict[str, Any]:
        """Build the current observation dict."""
        if self._current_step < self._num_steps:
            observation = dict(self._market_path[self._current_step])
        else:
            observation = {}
        
        return {
            "current_step": self._current_step,
            "done": self._done,
            "observation": observation,
            "cash_balance": self._cash,
            "positions": dict(self._positions),
        }
    
    def _build_state(self) -> dict[str, Any]:
        """Build the current full state dict."""
        state = self._build_observation()
        state["action_history"] = list(self._action_history)
        return state
    
    @property
    def market_path(self) -> list[dict[str, float]]:
        """Return a deep copy of the market path."""
        return [dict(step) for step in self._market_path]
    
    @property
    def num_steps(self) -> int:
        """Return the number of steps in the market path."""
        return self._num_steps


class MarketPathEnvironment(TradingEnvironment):
    """
    Alias for TradingEnvironment for backwards compatibility.
    
    This class is provided as an alias to support both naming conventions
    mentioned in the requirements.
    """
    pass
