from __future__ import annotations

from typing import Dict, List, Optional

from services.core.broker.base import Broker
from services.core.broker.types import ExecutionEvent, OrderRequest
from services.core.state import State
from services.core.transitions import apply_action


class LocalPaperBroker(Broker):
    def execute(
        self,
        orders: List[OrderRequest],
        price_context: Dict[str, float],
        starting_state: Optional[State] = None,
    ) -> List[ExecutionEvent]:
        events: List[ExecutionEvent] = []
        rolling_state = starting_state
        for order in orders:
            price = price_context.get(order.symbol, order.limit_price)
            event_id = f"{order.run_id}:{order.step_index}:{order.action_index}"
            if rolling_state is not None:
                cash_before = rolling_state.cash_balance
                exposure_before = rolling_state.exposure_value(price_context)
                positions_before = dict(rolling_state.positions)
                action = _order_to_action(order, price)
                transition = apply_action(rolling_state, action)
                rolling_state = transition.next_state
                cash_after = rolling_state.cash_balance
                exposure_after = rolling_state.exposure_value(price_context)
                positions_after = dict(rolling_state.positions)
            else:
                cash_before = 0.0
                exposure_before = 0.0
                positions_before = {}
                cash_after = 0.0
                exposure_after = 0.0
                positions_after = {}
            why = "paper fill"
            events.append(
                ExecutionEvent(
                    event_id=event_id,
                    run_id=order.run_id,
                    step_index=order.step_index,
                    action_index=order.action_index,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=price,
                    status="FILLED",
                    cash_before=cash_before,
                    cash_after=cash_after,
                    positions_before=positions_before,
                    positions_after=positions_after,
                    exposure_before=exposure_before,
                    exposure_after=exposure_after,
                    why=why,
                )
            )
        return events


def _order_to_action(order: OrderRequest, price: float) -> object:
    from services.core.actions import PlaceBuy, PlaceSell

    if order.side == "BUY":
        return PlaceBuy(symbol=order.symbol, quantity=order.quantity, price=price)
    return PlaceSell(symbol=order.symbol, quantity=order.quantity, price=price)
