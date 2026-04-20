from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from ewm_core.agents import LLMAgent


def _make_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


class TestLLMAgent:
    def test_decide_returns_required_keys(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "buy\nSMA5 crossed above SMA10 indicating upward momentum."
            )
            agent = LLMAgent(api_key="test-key")
            obs: dict[str, Any] = {
                "symbol": "AAPL", "price": 150.0,
                "sma5": 151.0, "sma10": 149.0,
                "volume": 1000000, "position": "flat",
            }
            decision = agent.decide(obs)

        assert set(decision.keys()) >= {"type", "symbol", "qty", "source", "reasoning"}

    def test_decide_valid_buy_action(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "buy\nPrice is trending upward."
            )
            agent = LLMAgent(api_key="test-key")
            decision = agent.decide({"symbol": "AAPL", "price": 150.0})

        assert decision["type"] == "buy"
        assert decision["qty"] == 1
        assert decision["source"] == "llm"

    def test_decide_valid_sell_action(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "sell\nPrice is declining below SMA10."
            )
            agent = LLMAgent(api_key="test-key")
            decision = agent.decide({"symbol": "AAPL", "price": 148.0})

        assert decision["type"] == "sell"
        assert decision["qty"] == 1

    def test_decide_hold_sets_qty_zero(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "hold\nNo clear signal in current conditions."
            )
            agent = LLMAgent(api_key="test-key")
            decision = agent.decide({"symbol": "AAPL", "price": 150.0})

        assert decision["type"] == "hold"
        assert decision["qty"] == 0

    def test_invalid_response_defaults_to_hold(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "STRONG BUY!!!\nThis is a great opportunity."
            )
            agent = LLMAgent(api_key="test-key")
            decision = agent.decide({"symbol": "AAPL", "price": 150.0})

        assert decision["type"] == "hold"

    def test_garbled_response_defaults_to_hold(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "I cannot determine the action."
            )
            agent = LLMAgent(api_key="test-key")
            decision = agent.decide({"symbol": "AAPL", "price": 150.0})

        assert decision["type"] == "hold"

    def test_decide_with_reason_returns_explanation(self) -> None:
        with patch("ewm_core.agents.llm_agent.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = _make_response(
                "buy\nMomentum is positive."
            )
            agent = LLMAgent(api_key="test-key")
            result = agent.decide_with_reason({"symbol": "AAPL", "price": 150.0})

        assert "decision" in result
        assert "explanation" in result
        assert result["explanation"] == "Momentum is positive."
