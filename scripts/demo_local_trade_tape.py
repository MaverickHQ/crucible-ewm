from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.artifacts import ArtifactWriter
from services.core.deltas.compute import compute_state_delta
from services.core.execution import execute_run
from services.core.market.path import MarketPath
from services.core.observability import (
    TapeRow,
    render_tape_row,
    write_report_md,
    write_tape_csv,
    write_tape_json,
)
from services.core.persistence import PolicyStore, RunStore, StateStore
from services.core.policy.versioning import ensure_policy_metadata
from services.core.simulator import simulate_plan
from services.core.state import RiskLimits, State
from services.core.strategy import evaluate_signals_with_rationale, load_strategy, signals_to_actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local trade tape demo.")
    parser.add_argument(
        "--fixture",
        default="examples/fixtures/trading_path.json",
        help="MarketPath fixture",
    )
    parser.add_argument(
        "--strategy",
        default="examples/strategies/threshold_demo.json",
        help="Strategy spec JSON",
    )
    parser.add_argument("--steps", type=int, default=10, help="Number of steps")
    return parser.parse_args()


def load_market_path(path: str) -> MarketPath:
    payload = json.loads(Path(path).read_text())
    return MarketPath(symbols=payload["symbols"], steps=payload["steps"])


def format_signal_map(signals: dict) -> dict:
    return {symbol: signal.value for symbol, signal in signals.items()}


def main() -> None:
    args = parse_args()
    fixture_path = Path(args.fixture)
    strategy_path = Path(args.strategy)

    market_path = load_market_path(str(fixture_path))
    strategy = load_strategy(str(strategy_path))

    data_dir = ROOT / "tmp" / "demo_local_tape"
    data_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = data_dir / "artifacts"
    tape_json_path = data_dir / "tape.json"
    tape_csv_path = data_dir / "tape.csv"
    report_path = data_dir / "report.md"

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

    rows: list[TapeRow] = []
    steps = min(args.steps, len(market_path.steps))

    print("step | prices | signals | actions | decision | why | delta | run_id | artifact_dir")
    print("-" * 120)

    for step_index in range(steps):
        prices = market_path.price_context(step_index)
        evaluation = evaluate_signals_with_rationale(
            strategy=strategy,
            state=state,
            price_ctx=prices,
            step_index=step_index,
            market_path=market_path,
        )
        signals = format_signal_map(evaluation.signals)
        rationales = evaluation.rationales

        actions = signals_to_actions(strategy, state, prices, evaluation.signals)
        action_payloads = [action.to_dict() for action in actions]

        if not actions:
            delta = compute_state_delta(state, state, prices)
            row = TapeRow(
                step_index=step_index,
                prices=prices,
                signals=signals,
                rationales=rationales,
                actions=action_payloads,
                decision="HOLD",
                why="strategy HOLD",
                explanation="",
                state_delta=delta,
                verifier_errors=[],
                run_id="-",
                artifact_dir=str(artifact_dir),
            )
            rows.append(row)
            print(render_tape_row(row))
            continue

        simulation = simulate_plan(
            state,
            actions,
            market_path,
            policy_id=policy["policy_id"],
            policy_version=policy["policy_version"],
            policy_hash=policy["policy_hash"],
        )
        run_store.save_run(simulation)
        artifacts = artifact_writer.write(simulation)

        decision = "APPROVED" if simulation.approved else "REJECTED"
        explanation = simulation.steps[-1].explanation if simulation.steps else ""
        verifier_errors = [
            {"code": error.code, "message": error.message}
            for error in (simulation.steps[-1].errors if simulation.steps else [])
        ]
        if simulation.approved and simulation.trajectory:
            final_state = simulation.trajectory[-1]
            delta = compute_state_delta(state, final_state, prices)
        else:
            delta = compute_state_delta(state, state, prices)
        why_parts = [
            f"{symbol}: {rationale}"
            for symbol, rationale in rationales.items()
            if signals.get(symbol) != "HOLD"
        ]
        why = "; ".join(why_parts) if why_parts else "strategy HOLD"
        if simulation.approved:
            why = f"{why} | verified OK"
        else:
            why = f"{why} | verification failed"

        row = TapeRow(
            step_index=step_index,
            prices=prices,
            signals=signals,
            rationales=rationales,
            actions=action_payloads,
            decision=decision,
            why=why,
            explanation=explanation,
            state_delta=delta,
            verifier_errors=verifier_errors,
            run_id=simulation.run_id,
            artifact_dir=str(artifacts["decision"]).rsplit("/", 1)[0],
        )
        rows.append(row)
        print(render_tape_row(row))

        if simulation.approved:
            execution = execute_run(run_store, state_store, simulation.run_id)
            if execution.state is not None:
                state = execution.state

    write_tape_json(tape_json_path, rows)
    write_tape_csv(tape_csv_path, rows)
    write_report_md(
        report_path,
        rows,
        strategy_name=strategy.metadata.name,
        fixture_name=fixture_path.name,
        steps=steps,
        final_state=state,
    )


if __name__ == "__main__":
    main()