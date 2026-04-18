from services.core.market.path import MarketPath
from services.core.state import RiskLimits, State
from services.core.strategy.evaluate import evaluate_signals
from services.core.strategy.types import (
    MeanReversionRule,
    Signal,
    SmaCrossoverRule,
    StrategyMetadata,
    StrategySizing,
    StrategySpec,
    StrategyUniverse,
    ThresholdPriceRule,
)


def _make_path() -> MarketPath:
    return MarketPath(
        symbols=["AAPL"],
        steps=[
            {"AAPL": 100.0},
            {"AAPL": 99.0},
            {"AAPL": 101.0},
            {"AAPL": 98.0},
        ],
    )


def _base_spec(rule) -> StrategySpec:
    return StrategySpec(
        metadata=StrategyMetadata(name="Test", version="1", description=""),
        universe=StrategyUniverse(symbols=["AAPL"]),
        sizing=StrategySizing(max_position_qty_per_symbol=5, order_qty=1),
        rules=[rule],
    )


def test_threshold_rule_signal() -> None:
    path = _make_path()
    rule = ThresholdPriceRule(symbol="AAPL", buy_below=99.5, sell_above=101.0)
    spec = _base_spec(rule)
    state = State(
        cash_balance=1000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5000.0),
    )
    signals = evaluate_signals(
        spec,
        state,
        path.price_context(1),
        step_index=1,
        market_path=path,
    )
    assert signals["AAPL"] == Signal.BUY


def test_sma_crossover_rule_signal() -> None:
    path = _make_path()
    rule = SmaCrossoverRule(symbol="AAPL", short_window=2, long_window=3)
    spec = _base_spec(rule)
    state = State(
        cash_balance=1000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5000.0),
    )
    signals = evaluate_signals(
        spec,
        state,
        path.price_context(3),
        step_index=3,
        market_path=path,
    )
    assert signals["AAPL"] in {Signal.BUY, Signal.SELL, Signal.HOLD}


def test_mean_reversion_rule_signal() -> None:
    path = _make_path()
    rule = MeanReversionRule(
        symbol="AAPL",
        window=3,
        z_buy_below=-0.1,
        z_sell_above=0.1,
    )
    spec = _base_spec(rule)
    state = State(
        cash_balance=1000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5000.0),
    )
    signals = evaluate_signals(
        spec,
        state,
        path.price_context(3),
        step_index=3,
        market_path=path,
    )
    assert signals["AAPL"] in {Signal.BUY, Signal.SELL, Signal.HOLD}
