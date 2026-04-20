"""Demo: LLMAgent making trading decisions on synthetic observations."""
from __future__ import annotations

import os

from ewm_core.agents import LLMAgent

OBSERVATIONS = [
    {
        "symbol": "AAPL",
        "price": 182.50,
        "sma5": 183.10,
        "sma10": 180.25,
        "volume": 52_000_000,
        "position": "flat",
    },
    {
        "symbol": "AAPL",
        "price": 178.00,
        "sma5": 179.50,
        "sma10": 181.00,
        "volume": 61_000_000,
        "position": "long",
    },
    {
        "symbol": "AAPL",
        "price": 185.00,
        "sma5": 184.20,
        "sma10": 182.50,
        "volume": 45_000_000,
        "position": "flat",
    },
]


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set")

    agent = LLMAgent(api_key=api_key)

    for i, obs in enumerate(OBSERVATIONS, 1):
        print(f"\n--- Decision {i} ---")
        print(f"Observation: {obs}")
        decision = agent.decide(obs)
        print(f"Action:      {decision['type']}  (qty={decision['qty']})")
        print(f"Reasoning:   {decision['reasoning']}")


if __name__ == "__main__":
    main()
