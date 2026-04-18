from __future__ import annotations

from typing import Dict

from ewm_core.state import State
from ewm_core.verifier import VerificationResult


def _format_currency(value: float) -> str:
    return f"{value:.2f}"


def explain_transition(
    prior_state: State,
    action: object,
    next_state: State,
    verification: VerificationResult,
    prices: Dict[str, float],
) -> str:
    if verification.accepted:
        cash_delta = next_state.cash_balance - prior_state.cash_balance
        exposure_delta = next_state.exposure - prior_state.exposure
        return (
            "Accepted: cash "
            f"{_format_currency(prior_state.cash_balance)} → "
            f"{_format_currency(next_state.cash_balance)} ({cash_delta:+.2f}), "
            f"exposure {prior_state.exposure:.2f} → {next_state.exposure:.2f} "
            f"({exposure_delta:+.2f})."
        )

    if not verification.errors:
        return "Rejected: transition failed verification."

    error_messages = ", ".join(f"{error.code}: {error.message}" for error in verification.errors)
    equity = prior_state.equity(prices)
    return (
        "Rejected: "
        f"{error_messages}. Equity={equity:.2f}, cash={prior_state.cash_balance:.2f}, "
        f"exposure={prior_state.exposure:.2f}."
    )
