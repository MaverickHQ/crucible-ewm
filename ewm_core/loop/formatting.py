from __future__ import annotations

from typing import Dict, List

from ewm_core.broker.types import ExecutionEvent
from ewm_core.loop.types import ExecutionRow


def render_execution_row(row: ExecutionRow) -> str:
    return " | ".join(
        [
            str(row.step_index),
            row.symbol,
            row.side,
            f"{row.quantity:.2f}",
            f"{row.price:.2f}",
            f"{row.cash_before:.2f}",
            f"{row.cash_after:.2f}",
            f"{row.exposure_before:.2f}",
            f"{row.exposure_after:.2f}",
            _format_positions(row.positions_before),
            _format_positions(row.positions_after),
            row.run_id,
            row.reason,
        ]
    )


def _format_positions(positions: Dict[str, float]) -> str:
    if not positions:
        return "-"
    parts = [f"{symbol} {qty:.2f}" for symbol, qty in sorted(positions.items())]
    return "; ".join(parts)


def render_execution_table(rows: List[ExecutionRow]) -> List[str]:
    lines = [
        "step | symbol | side | qty | price | cash_before | cash_after | "
        "exposure_before | exposure_after | positions_before | positions_after | run_id | why",
        "-" * 150,
    ]
    lines.extend(render_execution_row(row) for row in rows)
    return lines


def render_execution_event(event: ExecutionEvent) -> str:
    return " | ".join(
        [
            str(event.step_index),
            event.symbol,
            event.side,
            f"{event.quantity:.2f}",
            f"{event.price:.2f}",
            event.status,
            f"{event.cash_before:.2f}",
            f"{event.cash_after:.2f}",
            f"{event.exposure_before:.2f}",
            f"{event.exposure_after:.2f}",
            event.event_id,
            event.run_id,
        ]
    )


def render_execution_events(events: List[ExecutionEvent]) -> List[str]:
    lines = [
        "step | symbol | side | qty | price | status | cash_before | cash_after | "
        "exposure_before | exposure_after | event_id | run_id",
        "-" * 160,
    ]
    lines.extend(render_execution_event(event) for event in events)
    return lines
