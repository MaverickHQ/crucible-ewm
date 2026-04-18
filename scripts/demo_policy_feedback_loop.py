#!/usr/bin/env python3
"""Demonstrate the policy feedback loop for Essay 10.

This script demonstrates the complete learning loop:
1. Uses existing learning fixture / experiment fixture
2. Exports learning dataset if needed
3. Runs learner stub if needed
4. Builds evidence_policy.json
5. Runs a small trading decision demo that:
   - loads a market observation
   - shows baseline/default decision
   - shows evidence-informed decision
6. Prints a readable explanation of how evidence changes the decision path

This is the key demonstration for Essay 10 - showing that the system now closes the loop:
experiment → evidence → decision policy → better decisions

Usage:
    python3 scripts/demo_policy_feedback_loop.py

Note: This is NOT RL training - this is deterministic policy feedback.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.learning.dataset_export import export_learning_dataset
from services.core.learning.stub_learner import run_stub_learner
from services.core.policy import (
    load_evidence_policy,
    apply_evidence_policy,
    get_baseline_decision,
    build_evidence_policy_from_learning_report,
)


# Paths for the demo
FIXTURE_PATH = Path("tests/fixtures/learning_experiment")
DATASET_PATH = Path("outputs/learning/demo_trajectories.jsonl")
REPORT_PATH = Path("outputs/learning/demo_learning_report.json")
POLICY_PATH = Path("outputs/learning/evidence_policy.json")


def ensure_learning_artefacts() -> bool:
    """Ensure learning artefacts exist (dataset, report, policy).
    
    Returns:
        True if all artefacts exist or were created successfully.
    """
    # Check if we have the learning fixture
    if not FIXTURE_PATH.exists():
        print(f"ERROR: Learning fixture not found: {FIXTURE_PATH}")
        return False
    
    # Step 1: Export learning dataset if needed
    if not DATASET_PATH.exists():
        print(f"Exporting learning dataset from fixtures...")
        export_learning_dataset(
            experiment_dir=FIXTURE_PATH,
            output_path=DATASET_PATH,
        )
        print(f"  → Dataset exported to: {DATASET_PATH}")
    
    # Step 2: Run learner stub if needed
    if not REPORT_PATH.exists():
        print(f"Running learner stub...")
        run_stub_learner(
            dataset_path=DATASET_PATH,
            output_path=REPORT_PATH,
        )
        print(f"  → Report generated at: {REPORT_PATH}")
    
    # Step 3: Build evidence policy if needed
    if not POLICY_PATH.exists():
        print(f"Building evidence policy...")
        build_evidence_policy_from_learning_report(
            report_path=REPORT_PATH,
            output_path=POLICY_PATH,
        )
        print(f"  → Policy created at: {POLICY_PATH}")
    
    return True


def demo_decisions() -> None:
    """Demonstrate policy-guided decisions vs baseline."""
    
    print(f"\n{'='*60}")
    print("POLICY FEEDBACK LOOP DEMONSTRATION")
    print(f"{'='*60}\n")
    
    # Sample observations (simulating trading decisions)
    observations = [
        {"symbol": "AAPL", "step": 0, "price": 150.0, "description": "AAPL at step 0"},
        {"symbol": "AAPL", "step": 1, "price": 151.0, "description": "AAPL at step 1"},
        {"symbol": "AAPL", "step": 2, "price": 152.0, "description": "AAPL at step 2"},
        {"symbol": "MSFT", "step": 0, "price": 300.0, "description": "MSFT at step 0"},
        {"symbol": "MSFT", "step": 3, "price": 305.0, "description": "MSFT at step 3"},
        {"symbol": "UNKNOWN", "step": 2, "price": 100.0, "description": "Unknown symbol at step 2"},
    ]
    
    # Load the evidence policy
    policy = load_evidence_policy(POLICY_PATH)
    
    print("EVIDENCE POLICY:")
    print(f"  Evidence runs: {policy.get('evidence_runs', 0)}")
    print(f"  Default action: {policy.get('default_action', 'hold')}")
    print(f"  Symbol preferences: {policy.get('action_preferences_by_symbol', {})}")
    print(f"  Step preferences: {policy.get('action_preferences_by_step', {})}")
    
    print(f"\n{'='*60}")
    print("DECISION COMPARISON")
    print(f"{'='*60}")
    print(f"{'Observation':<35} | {'Baseline':<8} | {'Evidence-Informed':<18} | Source")
    print("-" * 90)
    
    policy_influenced_count = 0
    
    for obs in observations:
        # Get baseline decision (no policy)
        baseline = get_baseline_decision(obs)
        
        # Get policy-informed decision
        policy_decision = apply_evidence_policy(obs, policy)
        
        # Track if policy influenced the decision
        if policy_decision["action"] != baseline["action"]:
            policy_influenced_count += 1
        
        # Print comparison
        desc = obs.get("description", f"{obs.get('symbol')} @ step {obs.get('step')}")
        print(f"{desc:<35} | {baseline['action']:<8} | {policy_decision['action']:<18} | {policy_decision['source']}")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total observations:     {len(observations)}")
    print(f"Policy-influenced:      {policy_influenced_count}")
    print(f"Baseline-only:          {len(observations) - policy_influenced_count}")
    
    print(f"\n{'='*60}")
    print("LOOP EXPLANATION")
    print(f"{'='*60}")
    print("""
This demonstration shows the complete learning loop:

1. EXPERIMENTS: The learning fixture contains experiment runs with 
   trajectories, decisions, and outcomes.

2. EVIDENCE: The learning dataset is exported from these experiments,
   then analyzed by the learner stub to produce a learning report.

3. POLICY: The evidence policy is built from the learning report,
   capturing the most common actions by symbol and step position.

4. DECISIONS: When making new trading decisions, the evidence policy
   can be consulted to influence actions based on past experiment evidence.

This is NOT RL training - it's deterministic policy feedback:
- No model weights are learned
- No gradient descent occurs  
- No exploration/exploitation tradeoff
- Simply: past experiment evidence influences future decisions

The loop is now CLOSED: experiment → evidence → decision policy → better decisions
""")


def main() -> int:
    """Main entry point for the policy feedback loop demo."""
    
    print("="*60)
    print("EVIDENCE POLICY FEEDBACK LOOP DEMO (v0.8.5)")
    print("="*60)
    print("""
This demo shows how experiment evidence can influence future trading decisions.
This is the final link in the learning loop architecture.
""")
    
    # Ensure all artefacts exist
    if not ensure_learning_artefacts():
        return 1
    
    # Run the demonstration
    demo_decisions()
    
    print("\n✓ Demo completed successfully!")
    print(f"\nEvidence policy location: {POLICY_PATH}")
    print("\nTo regenerate:")
    print(f"  python3 scripts/export_learning_dataset.py")
    print(f"  python3 scripts/run_learning_stub.py")
    print(f"  python3 scripts/build_evidence_policy.py \\")
    print(f"    --learning-report {REPORT_PATH} --output {POLICY_PATH}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
