from ewm_core.actions.types import PlaceBuy, PlaceSell
from ewm_core.state.models import State
from ewm_core.strategy.evaluate import signals_to_actions
from ewm_core.strategy.types import (
    Signal,
    StrategyMetadata,
    StrategySizing,
    StrategySpec,
    StrategyUniverse,
)

DEFAULT_RISK_LIMITS = {
    "max_leverage": 2.0,
    "max_position_pct": 0.8,
    "max_position_value": 5000.0,
}


def _make_strategy(
    max_qty: float = 2,
    order_qty: float = 1,
    max_exposure: float | None = None,
) -> StrategySpec:
    return StrategySpec(
        metadata=StrategyMetadata(name="Test", version="1", description=""),
        universe=StrategyUniverse(symbols=["AAPL", "MSFT"]),
        sizing=StrategySizing(
            max_position_qty_per_symbol=max_qty,
            order_qty=order_qty,
            max_new_exposure_per_step=max_exposure,
        ),
        rules=[
            {
                "type": "threshold_price",
                "symbol": "AAPL",
                "buy_below": 100.0,
                "sell_above": 110.0,
            }
        ],
    )


def test_signals_to_actions_respects_cash() -> None:
    strategy = _make_strategy()
    state = State(
        cash_balance=50.0,
        positions={"AAPL": 0.0, "MSFT": 0.0},
        exposure=0.0,
        risk_limits=DEFAULT_RISK_LIMITS,
    )
    signals = {"AAPL": Signal.BUY, "MSFT": Signal.HOLD}
    actions = signals_to_actions(strategy, state, {"AAPL": 100.0, "MSFT": 200.0}, signals)
    assert actions == []


def test_signals_to_actions_respects_position_limits() -> None:
    strategy = _make_strategy(max_qty=1)
    state = State(
        cash_balance=1000.0,
        positions={"AAPL": 1.0, "MSFT": 0.0},
        exposure=100.0,
        risk_limits=DEFAULT_RISK_LIMITS,
    )
    signals = {"AAPL": Signal.BUY, "MSFT": Signal.HOLD}
    actions = signals_to_actions(strategy, state, {"AAPL": 100.0, "MSFT": 200.0}, signals)
    assert actions == []


def test_signals_to_actions_emits_buy_and_sell() -> None:
    strategy = _make_strategy()
    state = State(
        cash_balance=1000.0,
        positions={"AAPL": 1.0, "MSFT": 2.0},
        exposure=300.0,
        risk_limits=DEFAULT_RISK_LIMITS,
    )
    signals = {"AAPL": Signal.BUY, "MSFT": Signal.SELL}
    actions = signals_to_actions(strategy, state, {"AAPL": 100.0, "MSFT": 200.0}, signals)
    assert any(isinstance(action, PlaceBuy) for action in actions)
    assert any(isinstance(action, PlaceSell) for action in actions)


def test_signals_to_actions_respects_exposure_cap() -> None:
    strategy = _make_strategy(max_exposure=50)
    state = State(
        cash_balance=1000.0,
        positions={"AAPL": 0.0, "MSFT": 0.0},
        exposure=0.0,
        risk_limits=DEFAULT_RISK_LIMITS,
    )
    signals = {"AAPL": Signal.BUY, "MSFT": Signal.BUY}
    actions = signals_to_actions(strategy, state, {"AAPL": 100.0, "MSFT": 40.0}, signals)
    assert all(isinstance(action, PlaceBuy) for action in actions)
    assert len(actions) == 1
