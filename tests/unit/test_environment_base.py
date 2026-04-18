"""
Unit tests for the BaseEnvironment abstract class.

This tests that the abstract interface is properly defined and that
concrete implementations can be created.
"""

import pytest

from ewm_core.environment import BaseEnvironment


class ConcreteEnvironment(BaseEnvironment):
    """Concrete implementation of BaseEnvironment for testing."""
    
    def __init__(self):
        self._state = {"step": 0, "data": "initial"}
    
    def reset(self) -> dict:
        self._state = {"step": 0, "data": "initial"}
        return self._state
    
    def state(self) -> dict:
        return self._state
    
    def step(self, action: dict) -> dict:
        self._state["step"] += 1
        self._state["action"] = action
        return self._state


def test_base_environment_is_abstract():
    """Test that BaseEnvironment cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseEnvironment()


def test_concrete_implementation_can_be_instantiated():
    """Test that a concrete implementation can be created."""
    env = ConcreteEnvironment()
    assert env is not None


def test_reset_returns_dict():
    """Test that reset() returns a dict."""
    env = ConcreteEnvironment()
    result = env.reset()
    assert isinstance(result, dict)


def test_state_returns_dict():
    """Test that state() returns a dict."""
    env = ConcreteEnvironment()
    result = env.state()
    assert isinstance(result, dict)


def test_step_returns_dict():
    """Test that step() returns a dict."""
    env = ConcreteEnvironment()
    result = env.step({"type": "test"})
    assert isinstance(result, dict)


def test_concrete_implementation_interface():
    """Test that concrete implementation has all required methods."""
    env = ConcreteEnvironment()
    
    # Check all required methods exist
    assert hasattr(env, "reset")
    assert hasattr(env, "state")
    assert hasattr(env, "step")
    assert callable(env.reset)
    assert callable(env.state)
    assert callable(env.step)
