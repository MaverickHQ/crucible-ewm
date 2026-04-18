from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from services.core.state import State


@dataclass(frozen=True)
class TapeRow:
    step_index: int
    prices: Dict[str, float]
    signals: Dict[str, str]
    rationales: Dict[str, str]
    actions: List[Dict[str, object]]
    decision: str
    why: str
    explanation: str
    state_delta: Dict[str, object]
    verifier_errors: List[Dict[str, str]]
    run_id: str
    artifact_dir: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "step_index": self.step_index,
            "prices": self.prices,
            "signals": self.signals,
            "rationales": self.rationales,
            "actions": self.actions,
            "decision": self.decision,
            "why": self.why,
            "explanation": self.explanation,
            "state_delta": self.state_delta,
            "verifier_errors": self.verifier_errors,
            "run_id": self.run_id,
            "artifact_dir": self.artifact_dir,
        }


def _compact_prices(prices: Dict[str, float]) -> str:
    return ", ".join(f"{symbol}={price:.2f}" for symbol, price in prices.items())


def _compact_signals(signals: Dict[str, str]) -> str:
    return ", ".join(f"{symbol}:{signal}" for symbol, signal in signals.items())


def _compact_actions(actions: List[Dict[str, object]]) -> str:
    if not actions:
        return "-"
    parts = []
    for action in actions:
        action_type = action.get("type", "")
        symbol = action.get("symbol", "")
        qty = action.get("quantity", "")
        price = action.get("price", "")
        side = "BUY" if action_type == "PlaceBuy" else "SELL"
        parts.append(f"{side} {qty} {symbol} @ {price}")
    return "; ".join(parts)


def _format_exposure(state_delta: Dict[str, object], decision: str) -> str:
    exposure = state_delta.get("exposure", {})
    delta = exposure.get("delta", 0.0)
    if decision in {"REJECTED", "HOLD"}:
        delta = 0.0
    return f"exposure {delta:+.2f}"


def render_tape_row(row: TapeRow) -> str:
    return " | ".join(
        [
            str(row.step_index),
            _compact_prices(row.prices),
            _compact_signals(row.signals),
            _compact_actions(row.actions),
            row.decision,
            row.why,
            _format_exposure(row.state_delta, row.decision),
            row.run_id,
            row.artifact_dir,
        ]
    )


def write_tape_json(path: Path, rows: List[TapeRow]) -> None:
    path.write_text(json.dumps([row.to_dict() for row in rows], indent=2))


def write_tape_csv(path: Path, rows: List[TapeRow]) -> None:
    fieldnames = [
        "step_index",
        "prices",
        "signals",
        "rationales",
        "actions",
        "decision",
        "why",
        "explanation",
        "state_delta",
        "verifier_errors",
        "run_id",
        "artifact_dir",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = row.to_dict()
            writer.writerow(
                {
                    "step_index": payload["step_index"],
                    "prices": json.dumps(payload["prices"], sort_keys=True),
                    "signals": json.dumps(payload["signals"], sort_keys=True),
                    "rationales": json.dumps(payload["rationales"], sort_keys=True),
                    "actions": json.dumps(payload["actions"], sort_keys=True),
                    "decision": payload["decision"],
                    "why": payload["why"],
                    "explanation": payload["explanation"],
                    "state_delta": json.dumps(payload["state_delta"], sort_keys=True),
                    "verifier_errors": json.dumps(payload["verifier_errors"], sort_keys=True),
                    "run_id": payload["run_id"],
                    "artifact_dir": payload["artifact_dir"],
                }
            )


def write_report_md(
    path: Path,
    rows: List[TapeRow],
    strategy_name: str,
    fixture_name: str,
    steps: int,
    final_state: State,
) -> None:
    approved_rows = [row for row in rows if row.decision == "APPROVED"]
    rejected_rows = [row for row in rows if row.decision == "REJECTED"]

    lines = [
        "# Trade Tape Report",
        "",
        f"- Strategy: **{strategy_name}**",
        f"- Fixture: **{fixture_name}**",
        f"- Steps: **{steps}**",
        f"- Final state: `{final_state.to_dict()}`",
        "",
        "## Replay tape",
        f"- `python3 scripts/replay_tape.py --tape {path.with_name('tape.json')}`",
        "",
        "## Replay executions",
        f"- `python3 scripts/replay_executions.py --executions "
        f"{path.with_name('executions.json')}` (includes execution events)",
        "",
        "## What you should see",
        "- Deterministic per-step signals and verifier decisions.",
        "- Approved steps update cash/exposure/positions.",
        "- Rejected steps capture verifier error codes.",
        "",
        "## Trade Tape",
        "",
        "| step | prices | signals | actions | decision | why | exposure | run_id | artifact_dir |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.step_index),
                    _compact_prices(row.prices),
                    _compact_signals(row.signals),
                    _compact_actions(row.actions),
                    row.decision,
                    row.why,
                    _format_exposure(row.state_delta, row.decision),
                    row.run_id,
                    row.artifact_dir,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Rejected steps",
        ]
    )
    if not rejected_rows:
        lines.append("- None")
    else:
        for row in rejected_rows:
            codes = ", ".join(
                f"{error['code']}: {error['message']}" for error in row.verifier_errors
            )
            lines.append(f"- Step {row.step_index}: {codes}")

    lines.extend(
        [
            "",
            "## Approved steps",
        ]
    )
    if not approved_rows:
        lines.append("- None")
    else:
        for row in approved_rows:
            lines.append(f"- Step {row.step_index}: {row.explanation}")

    lines.extend(
        [
            "",
            "## Artifacts",
            f"- tape.json: `{path.with_name('tape.json')}`",
            f"- tape.csv: `{path.with_name('tape.csv')}`",
        ]
    )

    path.write_text("\n".join(lines))
