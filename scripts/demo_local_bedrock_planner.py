from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.artifacts import ArtifactWriter
from services.core.market import MarketPath
from services.core.persistence import PolicyStore, RunStore, StateStore
from services.core.planner import BedrockPlanner, run_planned_simulation
from services.core.policy.versioning import ensure_policy_metadata
from services.core.state import RiskLimits, State

BASE_DIR = ROOT
DATA_DIR = BASE_DIR / "tmp" / "demo_local_bedrock"
FIXTURE_PATH = BASE_DIR / "examples" / "fixtures" / "trading_path.json"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_PATH = DATA_DIR / "state.json"
RUNS_PATH = DATA_DIR / "runs.json"
POLICIES_PATH = DATA_DIR / "policies.json"


def _ensure_enabled() -> bool:
    if os.getenv("ENABLE_BEDROCK_PLANNER") != "1":
        print("Bedrock planner disabled; set ENABLE_BEDROCK_PLANNER=1 to enable.")
        return False
    missing = [
        name
        for name in ("AWS_REGION", "BEDROCK_MODEL_ID")
        if not os.getenv(name)
    ]
    if missing:
        print(
            "Missing required env vars for Bedrock planner: "
            + ", ".join(missing)
            + "."
        )
        return False
    return True


def _format_action(index: int, action: object, market_path: MarketPath) -> str:
    symbol = getattr(action, "symbol", None)
    side = "BUY" if action.__class__.__name__ == "PlaceBuy" else "SELL"
    qty = getattr(action, "quantity", "?")
    price_context = market_path.price_context(index)
    price = price_context.get(symbol) if price_context else None
    if price is None:
        price = getattr(action, "price", 0.0)
    return f"{index + 1}) {side} {qty} {symbol} @ {price}"


def _explain(simulation) -> str:
    if not simulation.steps:
        return ""
    if simulation.approved:
        return simulation.steps[-1].explanation
    rejected_index = simulation.rejected_step_index
    if rejected_index is not None and rejected_index < len(simulation.steps):
        return simulation.steps[rejected_index].explanation
    return simulation.steps[-1].explanation


def _planner_metadata(metadata: dict | None) -> str:
    if not metadata:
        return "{}"
    safe_metadata = {
        key: value
        for key, value in metadata.items()
        if key not in {"request_id", "account_id", "arn"}
    }
    return json.dumps(safe_metadata, sort_keys=True)


def main() -> None:
    if not _ensure_enabled():
        return

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
    planner = BedrockPlanner(
        model_id=os.environ["BEDROCK_MODEL_ID"],
        region_name=os.environ["AWS_REGION"],
    )

    print("Bedrock planner demo: initialized policy and state")

    for goal, label in [
        ("reject", "Bedrock Planner Scenario A (expected rejection)"),
        ("approve", "Bedrock Planner Scenario B (expected approval)"),
    ]:
        planner_result, simulation = run_planned_simulation(
            planner=planner,
            initial_state=initial_state,
            market_path=market_path,
            policy=policy,
            goal=goal,
            state_summary=initial_state.to_dict(),
        )

        run_store.save_run(simulation)
        artifacts = artifact_writer.write(simulation)

        print(f"\n{label}")
        print(f"Planner={planner_result.planner_name} goal={goal}")
        print(f"Planner metadata: {_planner_metadata(planner_result.metadata)}")
        print("Plan:")
        for index, action in enumerate(planner_result.plan):
            print(f"  {_format_action(index, action, market_path)}")

        decision = "approved" if simulation.approved else "rejected"
        explanation = _explain(simulation)
        print(f"Decision: {decision} run_id={simulation.run_id}")
        print(f"Explanation: {explanation}")
        if planner_result.rejection:
            print(
                "Planner rejection: "
                f"step={planner_result.rejection.rejected_step_index} "
                f"violations={planner_result.rejection.violations}"
            )

        print(
            "Artifacts: "
            f"trajectory={artifacts['trajectory']} "
            f"decision={artifacts['decision']} "
            f"deltas={artifacts['deltas']}"
        )


if __name__ == "__main__":
    main()