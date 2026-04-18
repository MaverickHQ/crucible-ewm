from ewm_core.market.path import MarketPath
from ewm_core.state import RiskLimits, State
from ewm_core.strategy import evaluate_signals_with_rationale
from ewm_core.strategy.types import (
    MeanReversionRule,
    SmaCrossoverRule,
    StrategyMetadata,
    StrategySizing,
    StrategySpec,
    StrategyUniverse,
    ThresholdPriceRule,
)


def _state() -> State:
    return State(
        cash_balance=1000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5000.0),
    )


def _path() -> MarketPath:
    return MarketPath(
        symbols=["AAPL"],
        steps=[{"AAPL": 100.0}, {"AAPL": 99.0}, {"AAPL": 101.0}, {"AAPL": 98.0}],
    )


def test_threshold_rationale_non_empty() -> None:
    spec = StrategySpec(
        metadata=StrategyMetadata(name="Test", version="1", description=""),
        universe=StrategyUniverse(symbols=["AAPL"]),
        sizing=StrategySizing(max_position_qty_per_symbol=5, order_qty=1),
        rules=[ThresholdPriceRule(symbol="AAPL", buy_below=100.5, sell_above=101.0)],
    )
    evaluation = evaluate_signals_with_rationale(
        spec,
        _state(),
        {"AAPL": 100.0},
        step_index=0,
        market_path=_path(),
    )
    assert evaluation.rationales["AAPL"]


def test_sma_rationale_non_empty() -> None:
    spec = StrategySpec(
        metadata=StrategyMetadata(name="Test", version="1", description=""),
        universe=StrategyUniverse(symbols=["AAPL"]),
        sizing=StrategySizing(max_position_qty_per_symbol=5, order_qty=1),
        rules=[SmaCrossoverRule(symbol="AAPL", short_window=2, long_window=3)],
    )
    evaluation = evaluate_signals_with_rationale(
        spec,
        _state(),
        {"AAPL": 98.0},
        step_index=3,
        market_path=_path(),
    )
    assert evaluation.rationales["AAPL"]


def test_mean_reversion_rationale_non_empty() -> None:
    spec = StrategySpec(
        metadata=StrategyMetadata(name="Test", version="1", description=""),
        universe=StrategyUniverse(symbols=["AAPL"]),
        sizing=StrategySizing(max_position_qty_per_symbol=5, order_qty=1),
        rules=[MeanReversionRule(symbol="AAPL", window=3, z_buy_below=-0.1, z_sell_above=0.1)],
    )
    evaluation = evaluate_signals_with_rationale(
        spec,
        _state(),
        {"AAPL": 98.0},
        step_index=3,
        market_path=_path(),
    )
    assert evaluation.rationales["AAPL"]
