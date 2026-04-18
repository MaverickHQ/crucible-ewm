from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.actions import PlaceBuy, PlaceSell
from services.core.artifacts import ArtifactWriter
from services.core.execution import execute_run
from services.core.market import MarketPath
from services.core.persistence import PolicyStore, RunStore, StateStore
from services.core.policy.versioning import ensure_policy_metadata
from services.core.simulator import simulate_plan
from services.core.state import RiskLimits, State

BASE_DIR = ROOT
DATA_DIR = BASE_DIR / "tmp" / "demo_local"
FIXTURE_PATH = BASE_DIR / "examples" / "fixtures" / "trading_path.json"
SCENARIO_DIR = BASE_DIR / "examples" / "scenarios"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_PATH = DATA_DIR / "state.json"
RUNS_PATH = DATA_DIR / "runs.json"
POLICIES_PATH = DATA_DIR / "policies.json"


def load_plan(path: Path):
    payload = json.loads(path.read_text())
    plan = []
    for item in payload["plan"]:
        if item["type"] == "PlaceBuy":
            plan.append(PlaceBuy(symbol=item["symbol"], quantity=item["quantity"], price=0.0))
        elif item["type"] == "PlaceSell":
            plan.append(PlaceSell(symbol=item["symbol"], quantity=item["quantity"], price=0.0))
    return plan


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    state_store = StateStore(STATE_PATH)
    run_store = RunStore(RUNS_PATH)
    policy_store = PolicyStore(POLICIES_PATH)
    artifact_writer = ArtifactWriter(ARTIFACT_DIR)

    policy = ensure_policy_metadata(
        {
            "policy_id": "default",
            "risk_limits": {
                "max_leverage": 2.0,
                "max_position_pct": 0.8,
                "max_position_value": 5_000.0,
            },
        }
    )
    policy_store.save_policy(policy)

    initial_state = State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    state_store.init_state(initial_state)

    market_path = MarketPath.from_fixture(FIXTURE_PATH)

    print("Step 1: Initialized default policy and state")

    for scenario_name, label in [
        ("scenario_reject.json", "Scenario A (expected rejection)"),
        ("scenario_approve.json", "Scenario B (expected approval)"),
    ]:
        plan = load_plan(SCENARIO_DIR / scenario_name)
        result = simulate_plan(
            initial_state,
            plan,
            market_path,
            policy_id=policy["policy_id"],
            policy_version=policy["policy_version"],
            policy_hash=policy["policy_hash"],
        )
        run_store.save_run(result)
        artifacts = artifact_writer.write(result)

        decision = "approved" if result.approved else "rejected"
        explanation = result.steps[-1].explanation if result.steps else ""
        print(f"\n{label} -> {decision} run_id={result.run_id}")
        print(f"Explanation: {explanation}")
        if not result.approved:
            rejected_step = result.rejected_step_index
            error_codes = [error.code for error in result.steps[rejected_step].errors]
            print(f"Rejected at step {rejected_step} with codes={error_codes}")
        else:
            print(f"Approved with {len(result.trajectory)} states")

        print(
            "Artifacts: "
            f"trajectory={artifacts['trajectory']} "
            f"decision={artifacts['decision']} "
            f"deltas={artifacts['deltas']}"
        )

    approved_run_id = [
        run_id
        for run_id in run_store._load_runs().keys()
        if run_store.get_run(run_id).approved
    ][-1]

    execution = execute_run(run_store, state_store, approved_run_id)
    print(f"\nStep 5: Execute approved run -> {execution.message}")
    print(f"New state: {execution.state.to_dict() if execution.state else None}")


if __name__ == "__main__":
    main()
