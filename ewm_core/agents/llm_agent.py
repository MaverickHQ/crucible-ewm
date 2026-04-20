from __future__ import annotations

import re
from typing import Any

import anthropic


_MODEL = "claude-haiku-4-5-20251001"
_VALID_ACTIONS = {"buy", "sell", "hold"}

_SYSTEM = (
    "You are a quantitative trading assistant. "
    "Given market data, respond with exactly one word: buy, sell, or hold. "
    "Then on a new line, give one sentence explaining your reasoning."
)


class LLMAgent:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def decide(self, observation: dict[str, Any]) -> dict[str, Any]:
        prompt = _build_prompt(observation)
        message = self._client.messages.create(
            model=_MODEL,
            max_tokens=128,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        action, reasoning = _parse_response(raw)

        symbol = observation.get("symbol", "")
        qty = 0 if action == "hold" else 1
        return {
            "type": action,
            "symbol": symbol,
            "qty": qty,
            "source": "llm",
            "reasoning": reasoning,
        }

    def decide_with_reason(self, observation: dict[str, Any]) -> dict[str, Any]:
        decision = self.decide(observation)
        return {"decision": decision, "explanation": decision["reasoning"]}


def _build_prompt(obs: dict[str, Any]) -> str:
    parts = [
        f"Symbol: {obs.get('symbol', 'unknown')}",
        f"Price: {obs.get('price', 'N/A')}",
        f"SMA5: {obs.get('sma5', 'N/A')}",
        f"SMA10: {obs.get('sma10', 'N/A')}",
        f"Volume: {obs.get('volume', 'N/A')}",
        f"Position: {obs.get('position', 'flat')}",
    ]
    return "\n".join(parts)


def _parse_response(raw: str) -> tuple[str, str]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    action = lines[0].lower() if lines else "hold"
    action = re.sub(r"[^a-z]", "", action)
    if action not in _VALID_ACTIONS:
        action = "hold"
    reasoning = lines[1] if len(lines) > 1 else raw
    return action, reasoning
