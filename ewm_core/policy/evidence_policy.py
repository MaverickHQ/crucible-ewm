"""Evidence Policy module for deterministic policy feedback from experiment evidence.

This module provides the final link in the learning loop:
- experiments produce evidence (trajectory datasets)
- evidence is analyzed by the learner stub to produce a learning report
- this module converts that report into a deterministic evidence policy
- the evidence policy can influence future trading decisions

This is NOT RL training - it's a deterministic policy-feedback scaffold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Default action when no evidence exists
DEFAULT_ACTION = "hold"


def load_evidence_policy(path: Path) -> Dict[str, Any]:
    """
    Load an evidence policy from a JSON file.
    
    Args:
        path: Path to the evidence policy JSON file.
        
    Returns:
        Dictionary containing the evidence policy.
        
    Raises:
        FileNotFoundError: If the policy file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Evidence policy not found: {path}")
    
    content = path.read_text()
    return json.loads(content)


def write_evidence_policy(policy: Dict[str, Any], path: Path) -> Path:
    """
    Write an evidence policy to a JSON file.
    
    Args:
        policy: Dictionary containing the evidence policy.
        path: Path to write the evidence policy JSON file.
        
    Returns:
        Path to the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure deterministic output (sorted keys)
    content = json.dumps(policy, indent=2, sort_keys=True)
    if not content.endswith("\n"):
        content += "\n"
    
    path.write_text(content)
    return path


def build_evidence_policy_from_learning_report(
    report_path: Path, 
    output_path: Path
) -> Path:
    """
    Build an evidence policy from a learning report.
    
    This function reads the learner stub's output (learning report) and
    converts it into a deterministic evidence policy that can be used
    to influence future trading decisions.
    
    The policy includes:
    - default_action: The most common action across all experiments
    - action_preferences_by_symbol: Most common action for each symbol
    - action_preferences_by_step: Most common action at each step position
    
    Args:
        report_path: Path to the learning report JSON.
        output_path: Path to write the evidence policy JSON.
        
    Returns:
        Path to the written evidence policy file.
        
    Raises:
        FileNotFoundError: If the report file doesn't exist.
    """
    report_path = Path(report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"Learning report not found: {report_path}")
    
    # Load the learning report
    report = json.loads(report_path.read_text())
    
    # Extract evidence runs count
    total_runs = report.get("total_runs", 0)
    
    # Determine default action (most common action)
    heuristics = report.get("heuristics", {})
    most_common = heuristics.get("most_common_action", {})
    default_action = most_common.get("type", DEFAULT_ACTION)
    
    # Build action preferences by symbol
    action_preferences_by_symbol: Dict[str, str] = {}
    by_symbol = heuristics.get("most_common_action_by_symbol", {})
    for symbol, data in by_symbol.items():
        if isinstance(data, dict) and "action" in data:
            action_preferences_by_symbol[symbol] = data["action"]
    
    # Build action preferences by step position
    action_preferences_by_step: Dict[str, str] = {}
    step_actions = heuristics.get("step_position_actions", {})
    for step_pos, data in step_actions.items():
        if isinstance(data, dict) and "action" in data:
            # Convert step position to string for JSON key consistency
            action_preferences_by_step[str(step_pos)] = data["action"]
    
    # Build the evidence policy
    policy: Dict[str, Any] = {
        "environment_type": "trading",
        "generated_from": str(report_path),
        "evidence_runs": total_runs,
        "default_action": default_action,
        "action_preferences_by_symbol": action_preferences_by_symbol,
        "action_preferences_by_step": action_preferences_by_step,
        # Include thresholds/heuristics from the report for transparency
        "thresholds": {
            "min_runs_for_confidence": 1,
            "max_step_position": max([int(k) for k in action_preferences_by_step.keys()]) + 1 
                                if action_preferences_by_step else 5,
        },
    }
    
    # Write the evidence policy
    return write_evidence_policy(policy, output_path)


def apply_evidence_policy(
    observation: Dict[str, Any], 
    policy: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply an evidence policy to an observation to produce a decision.
    
    This function uses the evidence policy to determine what action
    should be taken based on the current observation.
    
    Decision logic (in order of precedence):
    1. If symbol exists in action_preferences_by_symbol, use that action
    2. If step_position exists in action_preferences_by_step, use that action
    3. Fall back to default_action
    
    Args:
        observation: Current market observation containing:
            - symbol: The trading symbol (e.g., "AAPL")
            - step: Current step position in the run
            - Other observation fields may be present but are ignored
        policy: The evidence policy dictionary.
        
    Returns:
        Dictionary containing the policy-informed decision:
        - action: The recommended action (e.g., "hold", "buy", "sell")
        - source: Where the decision came from ("symbol", "step", or "default")
        - policy_used: Whether a policy was applied
    """
    # Get symbol from observation
    symbol = observation.get("symbol", "")
    step = observation.get("step", observation.get("step_index", 0))
    
    # Get policy fields
    default_action = policy.get("default_action", DEFAULT_ACTION)
    action_preferences_by_symbol = policy.get("action_preferences_by_symbol", {})
    action_preferences_by_step = policy.get("action_preferences_by_step", {})
    
    # Decision logic in order of precedence
    decision: Dict[str, Any] = {
        "policy_used": False,
        "source": "default",
        "action": default_action,
    }
    
    # Check symbol-based preference first
    if symbol and symbol in action_preferences_by_symbol:
        decision["policy_used"] = True
        decision["source"] = "symbol"
        decision["action"] = action_preferences_by_symbol[symbol]
    # Check step-based preference second
    elif str(step) in action_preferences_by_step:
        decision["policy_used"] = True
        decision["source"] = "step"
        decision["action"] = action_preferences_by_step[str(step)]
    # Fall back to default
    else:
        decision["action"] = default_action
    
    return decision


def get_baseline_decision(observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a baseline decision without using evidence policy.
    
    This represents the default behavior before evidence is applied.
    
    Args:
        observation: Current market observation.
        
    Returns:
        Dictionary containing the baseline decision:
        - action: The default action ("hold")
        - source: "baseline"
    """
    return {
        "action": DEFAULT_ACTION,
        "source": "baseline",
        "policy_used": False,
    }
