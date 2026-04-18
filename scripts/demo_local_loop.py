from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.loop import run_loop
from services.core.loop.formatting import (
    render_execution_events,
    render_execution_table,
)
from services.core.loop.ledger import write_execution_bundle, write_execution_ledger
from services.core.market.path import MarketPath
from services.core.observability import (
    render_tape_row,
    write_report_md,
    write_tape_csv,
    write_tape_json,
)
from services.core.strategy import load_strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local loop demo.")
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


def main() -> None:
    args = parse_args()
    fixture_path = Path(args.fixture)
    strategy_path = Path(args.strategy)

    market_path = load_market_path(str(fixture_path))
    strategy = load_strategy(str(strategy_path))

    data_dir = ROOT / "tmp" / "demo_local_loop"
    data_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = data_dir / "artifacts"
    tape_json_path = data_dir / "tape.json"
    tape_csv_path = data_dir / "tape.csv"
    report_path = data_dir / "report.md"
    executions_path = data_dir / "executions.json"

    steps = min(args.steps, len(market_path.steps))
    result = run_loop(
        market_path=market_path,
        strategy=strategy,
        steps=steps,
        data_dir=data_dir,
    )

    print("step | prices | signals | actions | decision | why | exposure | run_id | artifact_dir")
    print("-" * 120)
    for row in result.tape_rows:
        print(render_tape_row(row))

    write_tape_json(tape_json_path, result.tape_rows)
    write_tape_csv(tape_csv_path, result.tape_rows)
    write_report_md(
        report_path,
        result.tape_rows,
        strategy_name=strategy.metadata.name,
        fixture_name=fixture_path.name,
        steps=steps,
        final_state=result.final_state,
    )
    write_execution_bundle(executions_path, result.execution_bundles)

    for row in result.tape_rows:
        if row.decision == "APPROVED":
            run_executions = [
                execution
                for execution in result.execution_rows
                if execution.run_id == row.run_id
            ]
            if run_executions:
                step_dir = Path(row.artifact_dir)
                step_path = step_dir / "executions.json"
                write_execution_ledger(step_path, run_executions)

    if result.execution_bundles:
        print("\nExecution Events")
        events = [
            event
            for bundle in result.execution_bundles
            for event in bundle.events
        ]
        for line in render_execution_events(events):
            print(line)

    print("\nExecution Ledger")
    for line in render_execution_table(result.execution_rows):
        print(line)


if __name__ == "__main__":
    main()