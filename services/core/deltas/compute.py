from __future__ import annotations

from typing import Dict

from services.core.state import State


def compute_state_delta(
    prior: State,
    next_state: State,
    prices: Dict[str, float],
) -> Dict[str, object]:
    prior_equity = prior.equity(prices)
    next_equity = next_state.equity(prices)

    symbols = set(prior.positions) | set(next_state.positions)
    positions = {}
    for symbol in symbols:
        before = prior.positions.get(symbol, 0.0)
        after = next_state.positions.get(symbol, 0.0)
        if before != after:
            positions[symbol] = {"before": before, "after": after, "delta": after - before}

    return {
        "cash": {
            "before": prior.cash_balance,
            "after": next_state.cash_balance,
            "delta": next_state.cash_balance - prior.cash_balance,
        },
        "equity": {
            "before": prior_equity,
            "after": next_equity,
            "delta": next_equity - prior_equity,
        },
        "exposure": {
            "before": prior.exposure,
            "after": next_state.exposure,
            "delta": next_state.exposure - prior.exposure,
        },
        "positions": positions,
    }
