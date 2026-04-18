from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.core.market import generate_market_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic price path fixtures.")
    parser.add_argument("--tickers", required=True, help="Comma-separated ticker symbols")
    parser.add_argument("--steps", required=True, type=int, help="Number of steps to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--out",
        default="examples/fixtures/trading_path.json",
        help="Output fixture path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()]
    if not tickers:
        raise SystemExit("--tickers must include at least one symbol")

    market_path = generate_market_path(
        tickers=tickers,
        n_steps=args.steps,
        seed=args.seed,
    )

    payload = {
        "symbols": market_path.symbols,
        "steps": market_path.steps,
    }

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))

    print(
        f"Wrote fixture: {output_path} "
        f"(tickers={','.join(market_path.symbols)}, steps={args.steps}, seed={args.seed})"
    )


if __name__ == "__main__":
    main()