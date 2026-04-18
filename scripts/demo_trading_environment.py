#!/usr/bin/env python3
"""
Demo script for TradingEnvironment.

This script demonstrates the basic usage of the TradingEnvironment class
with a deterministic market path fixture.

The environment:
- Loads a deterministic market path from a fixture
- Resets to initial state
- Performs 2-3 step calls with dummy actions
- Prints readable state transitions
"""

import json
from pathlib import Path

from services.core.environment import TradingEnvironment


def load_fixture(fixture_path: str) -> list[dict]:
    """Load market path from fixture JSON."""
    path = Path(fixture_path)
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    
    with open(path) as f:
        data = json.load(f)
    
    # Extract just the price data (without timestamp/volume for the environment)
    steps = []
    for step in data["steps"]:
        price_step = {k: v for k, v in step.items() if k not in ("timestamp", "volume")}
        steps.append(price_step)
    
    return steps


def main():
    """Run the demo."""
    print("=" * 60)
    print("TradingEnvironment Demo")
    print("=" * 60)
    
    # Load fixture
    fixture_path = "examples/fixtures/trading_environment_path.json"
    market_path = load_fixture(fixture_path)
    
    print(f"\nLoaded market path with {len(market_path)} steps:")
    for i, step in enumerate(market_path):
        print(f"  Step {i}: {step}")
    
    # Create environment
    env = TradingEnvironment(
        market_path=market_path,
        initial_cash=10_000.0,
        initial_positions={"AAPL": 0, "MSFT": 0}
    )
    
    print("\n" + "-" * 60)
    print("Step 1: Reset environment")
    print("-" * 60)
    initial_state = env.reset()
    print(f"Current step: {initial_state['current_step']}")
    print(f"Done: {initial_state['done']}")
    print(f"Observation: {initial_state['observation']}")
    print(f"Cash balance: ${initial_state['cash_balance']:,.2f}")
    print(f"Positions: {initial_state['positions']}")
    
    # Action 1: Hold
    print("\n" + "-" * 60)
    print("Step 2: Take action - HOLD")
    print("-" * 60)
    action1 = {"type": "hold"}
    result1 = env.step(action1)
    print(f"Applied action: {result1['applied_action']}")
    print(f"Step index: {result1['step_index']}")
    print(f"Done: {result1['done']}")
    print(f"Observation: {result1['observation']}")
    print(f"Action history: {result1['info']['action_history']}")
    
    # Action 2: Observe
    print("\n" + "-" * 60)
    print("Step 3: Take action - OBSERVE")
    print("-" * 60)
    action2 = {"type": "observe"}
    result2 = env.step(action2)
    print(f"Applied action: {result2['applied_action']}")
    print(f"Step index: {result2['step_index']}")
    print(f"Done: {result2['done']}")
    print(f"Observation: {result2['observation']}")
    print(f"Action history: {result2['info']['action_history']}")
    
    # Action 3: Buy
    print("\n" + "-" * 60)
    print("Step 4: Take action - BUY AAPL")
    print("-" * 60)
    action3 = {"type": "buy", "symbol": "AAPL", "qty": 1}
    result3 = env.step(action3)
    print(f"Applied action: {result3['applied_action']}")
    print(f"Step index: {result3['step_index']}")
    print(f"Done: {result3['done']}")
    print(f"Observation: {result3['observation']}")
    print(f"Action history: {result3['info']['action_history']}")
    
    # Check state() method
    print("\n" + "-" * 60)
    print("Step 5: Check state() method")
    print("-" * 60)
    current_state = env.state()
    print(f"Current step: {current_state['current_step']}")
    print(f"Done: {current_state['done']}")
    print(f"Cash balance: ${current_state['cash_balance']:,.2f}")
    print(f"Positions: {current_state['positions']}")
    print(f"Full action history: {current_state['action_history']}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
