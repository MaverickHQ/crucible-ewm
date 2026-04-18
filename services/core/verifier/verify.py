from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Union

from services.core.actions import PlaceBuy, PlaceSell
from services.core.state import State

Action = Union[PlaceBuy, PlaceSell]


@dataclass(frozen=True)
class VerificationError:
    code: str
    message: str


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    errors: List[VerificationError] = field(default_factory=list)


def verify_transition(state: State, action: Action) -> VerificationResult:
    errors: List[VerificationError] = []

    if action.quantity <= 0 or action.price <= 0:
        errors.append(
            VerificationError(
                code="invalid_action",
                message="Quantity and price must be positive.",
            )
        )

    if not action.symbol:
        errors.append(VerificationError(code="invalid_action", message="Symbol is required."))

    prices = {action.symbol: action.price}
    equity = state.equity(prices)

    if isinstance(action, PlaceBuy):
        cost = action.quantity * action.price
        if cost > state.cash_balance:
            errors.append(
                VerificationError(
                    code="insufficient_cash",
                    message="Cash balance is insufficient.",
                )
            )
        projected_positions = dict(state.positions)
        projected_positions[action.symbol] = (
            projected_positions.get(action.symbol, 0.0) + action.quantity
        )
    elif isinstance(action, PlaceSell):
        current_qty = state.positions.get(action.symbol, 0.0)
        if action.quantity > current_qty:
            errors.append(
                VerificationError(
                    code="insufficient_position",
                    message="Cannot sell more than current position.",
                )
            )
        projected_positions = dict(state.positions)
        projected_positions[action.symbol] = current_qty - action.quantity
    else:
        errors.append(
            VerificationError(
                code="invalid_action",
                message="Unsupported action type.",
            )
        )
        projected_positions = dict(state.positions)

    projected_exposure = sum(
        abs(qty * prices.get(symbol, 0.0)) for symbol, qty in projected_positions.items()
    )
    projected_equity = equity

    if projected_equity <= 0:
        errors.append(
            VerificationError(
                code="invalid_equity",
                message="Equity must remain positive.",
            )
        )
    else:
        leverage = projected_exposure / projected_equity if projected_equity else float("inf")
        if leverage > state.risk_limits.max_leverage:
            errors.append(
                VerificationError(
                    code="leverage_limit",
                    message="Projected leverage exceeds limit.",
                )
            )

        for symbol, qty in projected_positions.items():
            position_value = abs(qty * prices.get(symbol, 0.0))
            if position_value > state.risk_limits.max_position_value:
                errors.append(
                    VerificationError(
                        code="position_value_limit",
                        message=f"Position value for {symbol} exceeds limit.",
                    )
                )
            if (
                projected_equity
                and (position_value / projected_equity) > state.risk_limits.max_position_pct
            ):
                errors.append(
                    VerificationError(
                        code="position_concentration",
                        message=(f"Position concentration for {symbol} exceeds limit."),
                    )
                )

    return VerificationResult(accepted=not errors, errors=errors)
