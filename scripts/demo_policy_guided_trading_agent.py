#!/usr/bin/env python3
"""Demonstrate the policy-guided trading agent.

This script demonstrates how a policy-guided agent consumes an evidence policy
and uses it to make trading decisions in the market-path environment.

This is NOT RL training - it's a deterministic policy-guided agent demonstration.

Usage:
    python3 scripts/demo_policy_guided_trading_agent.py

What it demonstrates:
1. Load the deterministic trading environment fixture
2. Load an evidence policy JSON
3. Instantiate PolicyGuidedAgent
4. Run environment steps
5. At each step print:
   - current observation
   - policy hint / explanation
   - chosen action
   - resulting next state

This demo clearly shows the policy being USED, not just loaded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.agent import PolicyGuidedAgent
from services.core.environment import TradingEnvironment
from services.core.policy import (
    load_evidence_policy,
    build_evidence_policy_from_learning_report,
)
from services.core.learning import export_learning_dataset, run_stub_learner


# Paths
FIXTURE_PATH = Path("tests/fixtures/learning_experiment")
TRADING_FIXTURE_PATH = Path("examples/fixtures/trading_environment_path.json")
DATASET_PATH = Path("outputs/learning/demo_trajectories.jsonl")
REPORT_PATH = Path("outputs/learning/demo_learning_report.json")
POLICY_PATH = Path("outputs/learning/evidence_policy.json")


def ensure_policy_exists() -> bool:
    """Ensure evidence policy exists (creates if needed)."""
    if POLICY_PATH.exists():
        return True

    # Ensure dataset and report exist
    if not DATASET_PATH.exists():
        print(f"Exporting learning dataset...")
        export_learning_dataset(FIXTURE_PATH, DATASET_PATH)
        print(f"  → Dataset: {DATASET_PATH}")

    if not REPORT_PATH.exists():
        print(f"Running learner stub...")
        run_stub_learner(DATASET_PATH, REPORT_PATH)
        print(f"  → Report: {REPORT_PATH}")

    # Build evidence policy
    print(f"Building evidence policy...")
    build_evidence_policy_from_learning_report(REPORT_PATH, POLICY_PATH)
    print(f"  → Policy: {POLICY_PATH}")

    return True


def load_trading_fixture() -> list[dict[str, float]]:
    """Load the trading environment fixture."""
    if not TRADING_FIXTURE_PATH.exists():
        # Create a minimal fixture
        return [
            {"AAPL": 150.0, "MSFT": 300.0},
            {"AAPL": 151.0, "MSFT": 301.0},
            {"AAPL": 152.0, "MSFT": 302.0},
            {"AAPL": 153.0, "MSFT": 303.0},
            {"AAPL": 154.0, "MSFT": 304.0},
        ]

    data = json.loads(TRADING_FIXTURE_PATH.read_text())
    return [
        {symbol: step.get(symbol, 0.0) for symbol in data.get("symbols", [])}
        for step in data.get("steps", [])
    ]


def main() -> int:
    """Main entry point."""
    print("=" * 70)
    print("POLICY-GUIDED TRADING AGENT DEMONSTRATION")
    print("=" * 70)
    print()
    print("This demo shows how a trading agent uses evidence policy to make decisions.")
    print()

    # Ensure policy exists
    print("-" * 70)
    print("STEP 1: Load Evidence Policy")
    print("-" * 70)

    if not ensure_policy_exists():
        print("ERROR: Failed to create evidence policy")
        return 1

    policy = load_evidence_policy(POLICY_PATH)
    print(f"Policy loaded from: {POLICY_PATH}")
    print(f"  Evidence runs: {policy.get('evidence_runs', 0)}")
    print(f"  Default action: {policy.get('default_action', 'hold')}")
    print(f"  Symbol preferences: {policy.get('action_preferences_by_symbol', {})}")
    print(f"  Step preferences: {policy.get('action_preferences_by_step', {})}")
    print()

    # Create the policy-guided agent
    print("-" * 70)
    print("STEP 2: Create Policy-Guided Agent")
    print("-" * 70)

    agent = PolicyGuidedAgent(policy)
    print(f"Agent created with policy")
    print(f"  Default action: {agent.default_action}")
    print()

    # Load trading environment
    print("-" * 70)
    print("STEP 3: Setup Trading Environment")
    print("-" * 70)

    market_path = load_trading_fixture()
    env = TradingEnvironment(market_path=market_path, initial_cash=10000.0)
    print(f"Trading environment initialized")
    print(f"  Market path: {len(market_path)} steps")
    print(f"  Initial cash: ${env._initial_cash:,.2f}")
    print()

    # Run agent through environment
    print("-" * 70)
    print("STEP 4: Run Agent Through Environment")
    print("-" * 70)

    state = env.reset()
    print(f"Initial state: step={state['current_step']}, done={state['done']}")
    print()

    step_count = 0
    max_steps = 5

    while step_count < max_steps and not state.get("done", False):
        # Get current observation
        obs = state.get("observation", {})
        current_step = state.get("current_step", step_count)

        # Build observation dict for agent (add symbol)
        if obs:
            # Get first symbol from observation
            symbol = list(obs.keys())[0] if obs else "UNKNOWN"
            price = obs.get(symbol, 0.0)
            agent_obs = {
                "symbol": symbol,
                "step": current_step,
                "price": price,
            }
        else:
            agent_obs = {"step": current_step}

        # Get agent decision with explanation
        result = agent.decide_with_reason(agent_obs)
        decision = result["decision"]
        explanation = result["explanation"]

        # Print step details
        print(f"--- Step {current_step} ---")
        print(f"  Observation: {agent_obs}")
        print(f"  Explanation: {explanation}")
        print(f"  Action: {decision}")
        print()

        # Execute action in environment
        action = {"type": decision["type"], "symbol": decision.get("symbol", "")}
        step_result = env.step(action)

        # Get next state
        state = env.state()
        step_count += 1

    print("-" * 70)
    print("STEP 5: Final State")
    print("-" * 70)

    final_state = env.state()
    print(f"Final step: {final_state.get('current_step', 'N/A')}")
    print(f"Episode done: {final_state.get('done', False)}")
    print(f"Action history: {len(final_state.get('action_history', []))} actions")
    for i, action in enumerate(final_state.get("action_history", [])):
        print(f"    {i}: {action}")
    print()

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("This demo proved:")
    print("  1. Evidence policy was loaded")
    print("  2. Policy-guided agent was instantiated")
    print("  3. Agent consulted policy at each step")
    print("  4. Agent made deterministic decisions based on policy")
    print("  5. Decisions were executed in the trading environment")
    print()
    print("The learning loop is now complete:")
    print("  experiment → evidence → policy → policy-guided decision")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
