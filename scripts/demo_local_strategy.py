from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.artifacts import ArtifactWriter
from services.core.execution import execute_run
from services.core.market.path import MarketPath
from services.core.persistence import PolicyStore, RunStore, StateStore
from services.core.policy.versioning import ensure_policy_metadata
from services.core.simulator import simulate_plan
from services.core.state import RiskLimits, State
from services.core.strategy import evaluate_signals, load_strategy, signals_to_actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic local strategy demo.")
    parser.add_argument(
        "--strategy",
        default="examples/strategies/threshold_demo.json",
        help="Path to strategy JSON",
    )
    parser.add_argument(
        "--fixture",
        default="examples/fixtures/trading_path.json",
        help="Path to market path fixture",
    )
    parser.add_argument("--steps", type=int, default=5, help="Number of steps to evaluate")
    return parser.parse_args()


def load_market_path(path: str) -> MarketPath:
    payload = json.loads(Path(path).read_text())
    return MarketPath(symbols=payload["symbols"], steps=payload["steps"])


def main() -> None:
    args = parse_args()
    market_path = load_market_path(args.fixture)
    strategy = load_strategy(args.strategy)

    data_dir = ROOT / "tmp" / "demo_local_strategy"
    data_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = data_dir / "artifacts"
    state_store = StateStore(data_dir / "state.json")
    run_store = RunStore(data_dir / "runs.json")
    policy_store = PolicyStore(data_dir / "policies.json")
    artifact_writer = ArtifactWriter(artifact_dir)

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

    state = State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    state_store.init_state(state)

    print("Strategy demo: initialized policy and state")
    actions_by_step = []
    max_steps = min(args.steps, len(market_path.steps))

    for step_index in range(max_steps):
        price_ctx = market_path.price_context(step_index)
        signals = evaluate_signals(
            strategy=strategy,
            state=state,
            price_ctx=price_ctx,
            step_index=step_index,
            market_path=market_path,
        )
        actions = signals_to_actions(strategy, state, price_ctx, signals)
        actions_by_step.append(actions)
        print(
            f"Step {step_index}: prices={price_ctx} "
            f"signals={{{', '.join(f'{k}:{v.value}' for k, v in signals.items())}}} "
            f"actions={[action.to_dict() for action in actions]}"
        )

    flat_actions = [action for step_actions in actions_by_step for action in step_actions][:2]
    print("\nSimulating first actions ->")
    simulation = simulate_plan(
        state,
        flat_actions,
        market_path,
        policy_id=policy["policy_id"],
        policy_version=policy["policy_version"],
        policy_hash=policy["policy_hash"],
    )
    run_store.save_run(simulation)
    artifacts = artifact_writer.write(simulation)

    decision = "approved" if simulation.approved else "rejected"
    explanation = simulation.steps[-1].explanation if simulation.steps else ""
    print(f"Decision: {decision} run_id={simulation.run_id}")
    print(f"Explanation: {explanation}")
    print(
        "Artifacts: "
        f"trajectory={artifacts['trajectory']} "
        f"decision={artifacts['decision']} "
        f"deltas={artifacts['deltas']}"
    )

    if simulation.approved:
        execution = execute_run(run_store, state_store, simulation.run_id)
        print(f"Execution: {execution.message}")


if __name__ == "__main__":
    main()