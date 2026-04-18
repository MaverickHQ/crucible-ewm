from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.artifacts import ArtifactWriter
from services.core.market import MarketPath
from services.core.persistence import PolicyStore, RunStore, StateStore
from services.core.planner import MockPlanner, run_planned_simulation
from services.core.policy.versioning import ensure_policy_metadata
from services.core.state import RiskLimits, State

BASE_DIR = ROOT
DATA_DIR = BASE_DIR / "tmp" / "demo_local_planner"
FIXTURE_PATH = BASE_DIR / "examples" / "fixtures" / "trading_path.json"
ARTIFACT_DIR = DATA_DIR / "artifacts"
STATE_PATH = DATA_DIR / "state.json"
RUNS_PATH = DATA_DIR / "runs.json"
POLICIES_PATH = DATA_DIR / "policies.json"


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
    planner = MockPlanner()

    print("Planner demo: initialized policy and state")

    def _effective_price(step_index: int, symbol: str, action: object) -> float:
        if symbol:
            price_context = market_path.price_context(step_index)
            if price_context:
                price = price_context.get(symbol)
                if price is not None:
                    return price
        if isinstance(action, dict):
            return float(action.get("price", 0.0) or 0.0)
        return float(getattr(action, "price", 0.0) or 0.0)

    def format_action(index: int, action: object) -> str:
        if isinstance(action, dict):
            side = "BUY" if action.get("type") == "PlaceBuy" else "SELL"
            qty = action.get("quantity", "?")
            symbol = action.get("symbol", "?")
            price = _effective_price(index - 1, symbol, action)
            return f"{index}) {side} {qty} {symbol} @ {price}"
        if hasattr(action, "symbol"):
            side = "BUY" if action.__class__.__name__ == "PlaceBuy" else "SELL"
            qty = getattr(action, "quantity", "?")
            symbol = getattr(action, "symbol", "?")
            price = _effective_price(index - 1, symbol, action)
            return f"{index}) {side} {qty} {symbol} @ {price}"
        return f"{index}) {action}"

    for goal, label in [
        ("reject", "Planner Scenario A (expected rejection)"),
        ("approve", "Planner Scenario B (expected approval)"),
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
        print(f"Planner={planner_result.planner_name} goal={planner_result.metadata.get('goal')}")
        print("Plan:")
        for index, action in enumerate(planner_result.plan, start=1):
            print(f"  {format_action(index, action)}")

        decision = "approved" if simulation.approved else "rejected"
        explanation = simulation.steps[-1].explanation if simulation.steps else ""
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