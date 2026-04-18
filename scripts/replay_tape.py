from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay trade tape from artifacts.")
    parser.add_argument("--tape", required=True, help="Path to tape.json")
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    parser.add_argument("--max-steps", type=int, default=None, help="Limit steps")
    return parser.parse_args()


def _compact_prices(prices: dict) -> str:
    return ", ".join(f"{symbol}={price:.2f}" for symbol, price in prices.items())


def _compact_signals(signals: dict) -> str:
    return ", ".join(f"{symbol}:{signal}" for symbol, signal in signals.items())


def _compact_actions(actions: list[dict]) -> str:
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


def _format_exposure(state_delta: dict, decision: str) -> str:
    exposure = state_delta.get("exposure", {})
    delta = exposure.get("delta", 0.0)
    if decision in {"REJECTED", "HOLD"}:
        delta = 0.0
    return f"exposure {delta:+.2f}"


def render_table(rows: list[dict]) -> None:
    print("step | prices | signals | actions | decision | why | exposure | run_id | artifact_dir")
    print("-" * 120)
    for row in rows:
        print(
            " | ".join(
                [
                    str(row.get("step_index")),
                    _compact_prices(row.get("prices", {})),
                    _compact_signals(row.get("signals", {})),
                    _compact_actions(row.get("actions", [])),
                    row.get("decision", ""),
                    row.get("why", ""),
                    _format_exposure(row.get("state_delta", {}), row.get("decision", "")),
                    row.get("run_id", ""),
                    row.get("artifact_dir", ""),
                ]
            )
        )


def main() -> None:
    args = parse_args()
    path = Path(args.tape)
    rows = json.loads(path.read_text())
    if args.max_steps is not None:
        rows = rows[: args.max_steps]

    if args.format == "json":
        print(json.dumps(rows, indent=2))
        return

    render_table(rows)


if __name__ == "__main__":
    main()