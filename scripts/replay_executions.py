from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.broker.types import ExecutionEvent
from services.core.loop.formatting import (
    render_execution_events,
    render_execution_row,
    render_execution_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay execution ledger.")
    parser.add_argument("--executions", required=True, help="Path to executions.json")
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    parser.add_argument("--max-rows", type=int, default=None, help="Limit rows")
    return parser.parse_args()


def render_table(rows: list[dict], events: list[ExecutionEvent]) -> None:
    if events:
        print("Execution Events")
        for line in render_execution_events(events):
            print(line)
        print("")

    print("Execution Ledger")
    for line in render_execution_table([_row_to_execution(row) for row in rows]):
        print(line)


def _row_to_execution(row: dict):
    from services.core.loop.types import ExecutionRow

    return ExecutionRow(
        step_index=row["step_index"],
        run_id=row["run_id"],
        decision=row.get("decision", ""),
        symbol=row["symbol"],
        side=row["side"],
        quantity=row["quantity"],
        price=row["price"],
        cash_before=row["cash_before"],
        cash_after=row["cash_after"],
        exposure_before=row.get("exposure_before", 0.0),
        exposure_after=row.get("exposure_after", 0.0),
        positions_before=row.get("positions_before", {}),
        positions_after=row.get("positions_after", {}),
        reason=row.get("reason", row.get("why", "")),
        verification=row.get("verification", ""),
    )


def _parse_events(payload: dict) -> list[ExecutionEvent]:
    events: list[ExecutionEvent] = []
    for bundle in payload.get("executions", []):
        for event in bundle.get("events", []):
            events.append(
                ExecutionEvent(
                    event_id=event["event_id"],
                    run_id=event["run_id"],
                    step_index=event["step_index"],
                    action_index=event["action_index"],
                    symbol=event["symbol"],
                    side=event["side"],
                    quantity=event["quantity"],
                    price=event["price"],
                    status=event["status"],
                    cash_before=event.get("cash_before", 0.0),
                    cash_after=event.get("cash_after", 0.0),
                    positions_before=event.get("positions_before", {}),
                    positions_after=event.get("positions_after", {}),
                    exposure_before=event.get("exposure_before", 0.0),
                    exposure_after=event.get("exposure_after", 0.0),
                    why=event.get("why", ""),
                )
            )
    return events


def _parse_ledger_rows(payload: dict) -> list[dict]:
    if isinstance(payload, list):
        return payload
    rows: list[dict] = []
    for bundle in payload.get("executions", []):
        rows.extend(bundle.get("ledger_rows", []))
    return rows


def main() -> None:
    args = parse_args()
    path = Path(args.executions)
    payload = json.loads(path.read_text())

    rows = _parse_ledger_rows(payload)
    if args.max_rows is not None:
        rows = rows[: args.max_rows]

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    events = _parse_events(payload) if isinstance(payload, dict) else []
    render_table(rows, events)


if __name__ == "__main__":
    main()