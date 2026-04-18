from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Union

from services.core.actions import PlaceBuy, PlaceSell
from services.core.state import State

Action = Union[PlaceBuy, PlaceSell]


@dataclass(frozen=True)
class TransitionResult:
    prior: State
    action: Action
    next_state: State
    prices: Dict[str, float]


def apply_action(state: State, action: Action) -> TransitionResult:
    prices = {action.symbol: action.price}
    positions = dict(state.positions)
    cash_balance = state.cash_balance

    if isinstance(action, PlaceBuy):
        cost = action.quantity * action.price
        positions[action.symbol] = positions.get(action.symbol, 0.0) + action.quantity
        cash_balance -= cost
    elif isinstance(action, PlaceSell):
        proceeds = action.quantity * action.price
        positions[action.symbol] = positions.get(action.symbol, 0.0) - action.quantity
        cash_balance += proceeds
    else:
        raise TypeError("Unsupported action type")

    next_state = State(
        cash_balance=cash_balance,
        positions=positions,
        exposure=sum(abs(qty * prices.get(symbol, 0.0)) for symbol, qty in positions.items()),
        risk_limits=state.risk_limits,
    )

    return TransitionResult(prior=state, action=action, next_state=next_state, prices=prices)
