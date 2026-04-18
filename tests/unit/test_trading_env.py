"""
Unit tests for the TradingEnvironment class.

These tests verify:
1) reset() returns expected initial structure
2) step() advances deterministically through market observations
3) state() reflects current environment step correctly
4) stepping through all observations eventually returns done == true
5) repeated reset() gives identical initial state
6) determinism check: same fixture + same actions => same outputs
7) actions are echoed consistently without introducing randomness
"""

import json
from pathlib import Path

import pytest

from ewm_core.environment import MarketPathEnvironment, TradingEnvironment

# Test fixtures
SIMPLE_PATH = [
    {"AAPL": 100.0, "MSFT": 200.0},
    {"AAPL": 101.0, "MSFT": 201.0},
    {"AAPL": 102.0, "MSFT": 202.0},
]

FIXTURE_PATH = Path("examples/fixtures/trading_environment_path.json")


def load_fixture_path() -> list[dict]:
    """Load market path from fixture file."""
    with open(FIXTURE_PATH) as f:
        data = json.load(f)
    # Extract price data only
    steps = []
    for step in data["steps"]:
        price_step = {k: v for k, v in step.items() if k not in ("timestamp", "volume")}
        steps.append(price_step)
    return steps


class TestTradingEnvironmentBasics:
    """Basic tests for TradingEnvironment initialization and interface."""

    def test_creation_with_simple_path(self):
        """Test that TradingEnvironment can be created with a simple market path."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        assert env is not None

    def test_creation_with_initial_cash(self):
        """Test that initial_cash is properly stored."""
        env = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=50_000.0)
        assert env is not None

    def test_creation_with_initial_positions(self):
        """Test that initial_positions are properly stored."""
        env = TradingEnvironment(
            market_path=SIMPLE_PATH,
            initial_positions={"AAPL": 10, "MSFT": 5}
        )
        assert env is not None

    def test_empty_path_raises_error(self):
        """Test that empty market path raises ValueError."""
        with pytest.raises(ValueError):
            TradingEnvironment(market_path=[])

    def test_market_path_property(self):
        """Test that market_path property returns a copy."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        path = env.market_path
        assert path == SIMPLE_PATH
        # Verify it's a copy, not a reference
        path[0]["AAPL"] = 999.0
        assert env.market_path[0]["AAPL"] == 100.0

    def test_num_steps_property(self):
        """Test that num_steps returns correct count."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        assert env.num_steps == 3


class TestReset:
    """Tests for reset() method."""

    def test_reset_returns_initial_state(self):
        """Test that reset() returns expected initial state structure."""
        env = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=10_000.0)
        state = env.reset()

        assert "current_step" in state
        assert "done" in state
        assert "observation" in state
        assert "cash_balance" in state
        assert "positions" in state

    def test_reset_sets_current_step_to_zero(self):
        """Test that reset() sets current_step to 0."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.step({"type": "hold"})  # Advance one step
        state = env.reset()
        assert state["current_step"] == 0

    def test_reset_sets_done_to_false(self):
        """Test that reset() sets done to False."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        # Advance to end
        for _ in range(5):
            env.step({"type": "hold"})
        state = env.reset()
        assert state["done"] is False

    def test_reset_restores_initial_cash(self):
        """Test that reset() restores initial cash balance."""
        env = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=10_000.0)
        env.step({"type": "hold"})
        state = env.reset()
        assert state["cash_balance"] == 10_000.0

    def test_reset_restores_initial_positions(self):
        """Test that reset() restores initial positions."""
        env = TradingEnvironment(
            market_path=SIMPLE_PATH,
            initial_positions={"AAPL": 10, "MSFT": 5}
        )
        env.step({"type": "hold"})
        state = env.reset()
        assert state["positions"] == {"AAPL": 10, "MSFT": 5}


class TestState:
    """Tests for state() method."""

    def test_state_returns_full_state(self):
        """Test that state() returns complete state including action history."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        env.step({"type": "hold"})
        
        state = env.state()
        
        assert "current_step" in state
        assert "done" in state
        assert "observation" in state
        assert "cash_balance" in state
        assert "positions" in state
        assert "action_history" in state

    def test_state_reflects_current_step(self):
        """Test that state() reflects current step index."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        assert env.state()["current_step"] == 0
        
        env.step({"type": "hold"})
        assert env.state()["current_step"] == 1
        
        env.step({"type": "hold"})
        assert env.state()["current_step"] == 2


class TestStep:
    """Tests for step() method."""

    def test_step_returns_expected_structure(self):
        """Test that step() returns expected dict structure."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        result = env.step({"type": "hold"})
        
        assert "observation" in result
        assert "done" in result
        assert "step_index" in result
        assert "applied_action" in result
        assert "info" in result

    def test_step_advances_step_index(self):
        """Test that step() advances the step index."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        result1 = env.step({"type": "hold"})
        assert result1["step_index"] == 1
        
        result2 = env.step({"type": "hold"})
        assert result2["step_index"] == 2

    def test_step_records_action(self):
        """Test that step() records the applied action."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        action = {"type": "buy", "symbol": "AAPL", "qty": 10}
        result = env.step(action)
        
        assert result["applied_action"] == action

    def test_step_echoes_action_in_info(self):
        """Test that action is echoed in info.action_history."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        env.step({"type": "hold"})
        env.step({"type": "buy", "symbol": "AAPL", "qty": 1})
        
        state = env.state()
        assert len(state["action_history"]) == 2
        assert state["action_history"][0] == {"type": "hold"}
        assert state["action_history"][1] == {"type": "buy", "symbol": "AAPL", "qty": 1}

    def test_step_advances_observation(self):
        """Test that step() advances to next market observation."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        obs0 = env.state()["observation"]
        assert obs0 == {"AAPL": 100.0, "MSFT": 200.0}
        
        env.step({"type": "hold"})
        obs1 = env.state()["observation"]
        assert obs1 == {"AAPL": 101.0, "MSFT": 201.0}

    def test_step_eventually_sets_done(self):
        """Test that stepping through all observations sets done=True."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        # 3 steps, 0-indexed means step 3 should be done
        for i in range(3):
            result = env.step({"type": "hold"})
        
        assert result["done"] is True

    def test_step_past_end_returns_done(self):
        """Test that stepping past the end keeps done=True."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        # Step past end
        for _ in range(5):
            result = env.step({"type": "hold"})
        
        assert result["done"] is True


class TestDeterminism:
    """Tests for determinism guarantees."""

    def test_repeated_reset_gives_identical_initial_state(self):
        """Test that repeated reset() produces identical initial state."""
        env = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=10_000.0)
        
        state1 = env.reset()
        state2 = env.reset()
        
        assert state1 == state2

    def test_same_path_same_actions_same_outputs(self):
        """Test determinism: same fixture + same actions = same outputs."""
        # Create two environments with same path
        env1 = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=10_000.0)
        env2 = TradingEnvironment(market_path=SIMPLE_PATH, initial_cash=10_000.0)
        
        # Reset both
        env1.reset()
        env2.reset()
        
        # Apply same sequence of actions
        actions = [
            {"type": "hold"},
            {"type": "buy", "symbol": "AAPL", "qty": 1},
            {"type": "observe"},
        ]
        
        for action in actions:
            result1 = env1.step(action)
            result2 = env2.step(action)
            
            assert result1["step_index"] == result2["step_index"]
            assert result1["done"] == result2["done"]
            assert result1["observation"] == result2["observation"]
            assert result1["applied_action"] == result2["applied_action"]

    def test_fixture_based_determinism(self):
        """Test determinism using the actual fixture file."""
        market_path = load_fixture_path()
        
        env1 = TradingEnvironment(market_path=market_path, initial_cash=10_000.0)
        env2 = TradingEnvironment(market_path=market_path, initial_cash=10_000.0)
        
        env1.reset()
        env2.reset()
        
        # Apply 3 steps
        for _ in range(3):
            action = {"type": "hold"}
            r1 = env1.step(action)
            r2 = env2.step(action)
            
            assert r1["observation"] == r2["observation"]
            assert r1["info"]["action_history"] == r2["info"]["action_history"]


class TestMarketPathEnvironment:
    """Tests for MarketPathEnvironment alias."""

    def test_market_path_environment_is_alias(self):
        """Test that MarketPathEnvironment is an alias for TradingEnvironment."""
        env = MarketPathEnvironment(market_path=SIMPLE_PATH)
        assert isinstance(env, TradingEnvironment)

    def test_market_path_environment_interface(self):
        """Test that MarketPathEnvironment has same interface."""
        env = MarketPathEnvironment(market_path=SIMPLE_PATH)
        assert hasattr(env, "reset")
        assert hasattr(env, "state")
        assert hasattr(env, "step")
        assert hasattr(env, "market_path")
        assert hasattr(env, "num_steps")


class TestEdgeCases:
    """Edge case tests."""

    def test_single_step_path(self):
        """Test environment with single step."""
        env = TradingEnvironment(market_path=[{"AAPL": 100.0}])
        env.reset()
        
        result = env.step({"type": "hold"})
        assert result["done"] is True

    def test_action_with_extra_fields(self):
        """Test that action extra fields are preserved."""
        env = TradingEnvironment(market_path=SIMPLE_PATH)
        env.reset()
        
        action = {"type": "custom", "foo": "bar", "baz": 123}
        result = env.step(action)
        
        assert result["applied_action"] == action
