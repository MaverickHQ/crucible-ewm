#!/usr/bin/env python3
"""Build evidence policy from a learning report.

This script reads the learner stub's output (learning report) and converts it
into a deterministic evidence policy that can influence future trading decisions.

Usage:
    python3 scripts/build_evidence_policy.py \
        --learning-report <path> \
        --output <path>

Example:
    python3 scripts/build_evidence_policy.py \
        --learning-report outputs/learning/demo_learning_report.json \
        --output outputs/learning/evidence_policy.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.core.policy import build_evidence_policy_from_learning_report


def main() -> int:
    """Main entry point for building evidence policy."""
    parser = argparse.ArgumentParser(
        description="Build evidence policy from a learning report"
    )
    parser.add_argument(
        "--learning-report",
        type=Path,
        required=True,
        help="Path to the learning report JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the evidence policy JSON file",
    )
    
    args = parser.parse_args()
    
    # Validate input path
    if not args.learning_report.exists():
        print(f"ERROR: Learning report not found: {args.learning_report}", file=sys.stderr)
        return 1
    
    # Build the evidence policy
    print(f"Building evidence policy from: {args.learning_report}")
    output_path = build_evidence_policy_from_learning_report(
        args.learning_report,
        args.output
    )
    
    # Load and print summary
    import json
    policy = json.loads(output_path.read_text())
    
    print(f"\nEvidence policy written to: {output_path}")
    print(f"\n{'='*50}")
    print("POLICY SUMMARY")
    print(f"{'='*50}")
    print(f"  Evidence runs:      {policy.get('evidence_runs', 0)}")
    print(f"  Default action:     {policy.get('default_action', 'N/A')}")
    
    # Print symbol preferences
    symbol_prefs = policy.get("action_preferences_by_symbol", {})
    if symbol_prefs:
        print(f"\n  Action preferences by symbol:")
        for symbol, action in sorted(symbol_prefs.items()):
            print(f"    {symbol}: {action}")
    
    # Print step preferences
    step_prefs = policy.get("action_preferences_by_step", {})
    if step_prefs:
        print(f"\n  Action preferences by step:")
        for step, action in sorted(step_prefs.items()):
            print(f"    step {step}: {action}")
    
    print(f"\n{'='*50}")
    print("Policy file is ready for use in demo_policy_feedback_loop.py")
    print(f"{'='*50}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
