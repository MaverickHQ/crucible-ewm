#!/usr/bin/env python3
"""End-to-end demonstration of the complete learning loop.

This script demonstrates the full learning loop from environment to improved decisions:
1. Uses the learning experiment fixture
2. Exports learning dataset
3. Runs learner stub
4. Builds evidence policy
5. Runs policy-guided agent using that evidence policy
6. Prints a clear readable summary

This is the definitive demo for Essay 10 - proving the complete loop works.

Usage:
    python3 scripts/demo_end_to_end_learning_loop.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.agent import PolicyGuidedAgent
from services.core.environment import TradingEnvironment
from services.core.learning import (
    select_learning_runs,
    export_learning_dataset,
    run_stub_learner,
)
from services.core.policy import (
    load_evidence_policy,
    build_evidence_policy_from_learning_report,
)


# Paths
FIXTURE_PATH = Path("tests/fixtures/learning_experiment")
OUTPUT_DIR = Path("outputs/learning")
DATASET_PATH = OUTPUT_DIR / "demo_trajectories.jsonl"
REPORT_PATH = OUTPUT_DIR / "demo_learning_report.json"
POLICY_PATH = OUTPUT_DIR / "evidence_policy.json"


def run_full_loop() -> dict:
    """
    Run the complete learning loop.
    
    Returns:
        Dictionary with all results for validation:
        - dataset_rows: Number of rows exported
        - report_data: The learning report
        - policy_data: The evidence policy
        - agent_decisions: List of agent decisions made
    """
    results = {
        "dataset_rows": 0,
        "report_data": None,
        "policy_data": None,
        "agent_decisions": [],
    }

    print("=" * 70)
    print("END-TO-END LEARNING LOOP DEMONSTRATION")
    print("=" * 70)
    print()
    print("This demo proves the complete learning loop:")
    print("  environment → trajectories → dataset → report → policy → decisions")
    print()

    # Step 1: Select valid runs
    print("-" * 70)
    print("STEP 1: Select Valid Runs from Experiment")
    print("-" * 70)

    selected_runs = select_learning_runs(
        FIXTURE_PATH,
        require_valid=True,
        include_truncated=True,
    )
    print(f"Selected {len(selected_runs)} valid runs from {FIXTURE_PATH}")
    for run in selected_runs:
        print(f"  - {run['run_id']}: {run['steps_executed']} steps")
    print()

    # Step 2: Export learning dataset
    print("-" * 70)
    print("STEP 2: Export Learning Dataset")
    print("-" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result_path = export_learning_dataset(
        FIXTURE_PATH,
        DATASET_PATH,
        require_valid=True,
    )

    # Count rows
    row_count = 0
    with open(result_path) as f:
        for line in f:
            if line.strip():
                row_count += 1

    results["dataset_rows"] = row_count
    print(f"Dataset exported to: {result_path}")
    print(f"Rows exported: {row_count}")
    print()

    # Step 3: Run learner stub
    print("-" * 70)
    print("STEP 3: Run Learner Stub")
    print("-" * 70)

    run_stub_learner(result_path, REPORT_PATH)

    # Load report for display
    with open(REPORT_PATH) as f:
        report_data = json.load(f)

    results["report_data"] = report_data
    print(f"Report generated at: {REPORT_PATH}")
    print(f"  Total runs: {report_data.get('total_runs', 0)}")
    print(f"  Total steps: {report_data.get('total_steps', 0)}")
    print(f"  Action counts: {report_data.get('action_counts', {})}")
    print(f"  Symbol counts: {report_data.get('symbol_counts', {})}")
    print()

    # Step 4: Build evidence policy
    print("-" * 70)
    print("STEP 4: Build Evidence Policy")
    print("-" * 70)

    build_evidence_policy_from_learning_report(REPORT_PATH, POLICY_PATH)

    # Load policy for display
    policy = load_evidence_policy(POLICY_PATH)
    results["policy_data"] = policy
    print(f"Policy created at: {POLICY_PATH}")
    print(f"  Evidence runs: {policy.get('evidence_runs', 0)}")
    print(f"  Default action: {policy.get('default_action', 'hold')}")
    print(f"  Symbol preferences: {policy.get('action_preferences_by_symbol', {})}")
    print(f"  Step preferences: {policy.get('action_preferences_by_step', {})}")
    print()

    # Step 5: Run policy-guided agent
    print("-" * 70)
    print("STEP 5: Run Policy-Guided Agent")
    print("-" * 70)

    agent = PolicyGuidedAgent(policy)

    # Create a simple market path for demonstration
    market_path = [
        {"AAPL": 150.0, "MSFT": 300.0},
        {"AAPL": 151.0, "MSFT": 301.0},
        {"AAPL": 152.0, "MSFT": 302.0},
        {"AAPL": 153.0, "MSFT": 303.0},
        {"AAPL": 154.0, "MSFT": 304.0},
    ]

    env = TradingEnvironment(market_path=market_path, initial_cash=10000.0)
    state = env.reset()

    print("Running agent through environment steps:")
    print()

    step_count = 0
    while step_count < 5 and not state.get("done", False):
        obs = state.get("observation", {})
        current_step = state.get("current_step", step_count)

        # Build agent observation
        if obs:
            symbol = list(obs.keys())[0] if obs else "UNKNOWN"
            price = obs.get(symbol, 0.0)
            agent_obs = {"symbol": symbol, "step": current_step, "price": price}
        else:
            agent_obs = {"step": current_step}

        # Get decision with reason
        result = agent.decide_with_reason(agent_obs)
        decision = result["decision"]
        explanation = result["explanation"]

        print(f"  Step {current_step}: {explanation}")
        results["agent_decisions"].append(decision)

        # Execute in environment
        action = {"type": decision["type"], "symbol": decision.get("symbol", "")}
        env.step(action)
        state = env.state()
        step_count += 1

    print()

    # Final summary
    print("=" * 70)
    print("LOOP SUMMARY")
    print("=" * 70)
    print()
    print(f"1. Experiment runs selected:  {len(selected_runs)}")
    print(f"2. Dataset rows exported:     {results['dataset_rows']}")
    print(f"3. Learning report generated: {'Yes' if report_data else 'No'}")
    print(f"4. Evidence policy built:     {'Yes' if policy else 'No'}")
    print(f"5. Policy-guided decisions:   {len(results['agent_decisions'])}")
    print()

    # Validation checks
    validation_passed = True
    print("-" * 70)
    print("VALIDATION CHECKS")
    print("-" * 70)

    if results["dataset_rows"] > 0:
        print(f"✓ Dataset exported: {results['dataset_rows']} rows")
    else:
        print(f"✗ Dataset export failed: {results['dataset_rows']} rows")
        validation_passed = False

    if policy and len(policy.get("action_preferences_by_symbol", {})) > 0:
        print(f"✓ Evidence policy built: {len(policy.get('action_preferences_by_symbol', {}))} symbol preferences")
    else:
        print(f"✗ Evidence policy empty or invalid")
        validation_passed = False

    if len(results["agent_decisions"]) > 0:
        policy_decisions = sum(1 for d in results["agent_decisions"] if d.get("policy_used", False))
        print(f"✓ Policy-guided decisions: {policy_decisions}/{len(results['agent_decisions'])} used policy")
    else:
        print(f"✗ No agent decisions made")
        validation_passed = False

    print()
    print("=" * 70)

    if validation_passed:
        print("END-TO-END DEMO PASSED")
    else:
        print("END-TO-END DEMO FAILED")
        return {"error": "Validation failed"}

    print("=" * 70)
    print()
    print("The learning loop is now complete:")
    print("  environment → trajectories → artifacts → evaluation")
    print("      → experiments → dataset → report → policy")
    print("      → policy-guided decisions")
    print()
    print("This is NOT RL training - it's deterministic policy feedback")
    print("that proves the architecture can close the loop from experiments")
    print("to future decisions (Essay 10).")

    return results


def main() -> int:
    """Main entry point."""
    try:
        results = run_full_loop()
        if "error" in results:
            return 1
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
