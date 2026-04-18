from pathlib import Path

from services.core.actions import PlaceBuy, PlaceSell
from services.core.market import MarketPath
from services.core.simulator import simulate_plan
from services.core.state import RiskLimits, State

FIXTURE_PATH = Path("examples/fixtures/trading_path.json")


def test_simulate_plan_all_steps_accepted():
    market_path = MarketPath.from_fixture(FIXTURE_PATH)
    state = State(cash_balance=10_000.0, risk_limits=RiskLimits(2.0, 0.6, 50_000.0))
    plan = [
        PlaceBuy(symbol="AAPL", quantity=10, price=0.0),
        PlaceBuy(symbol="MSFT", quantity=5, price=0.0),
    ]

    result = simulate_plan(state, plan, market_path)

    assert result.approved
    assert result.rejected_step_index is None
    assert len(result.trajectory) == len(plan) + 1


def test_simulate_plan_rejects_on_invalid_step():
    market_path = MarketPath.from_fixture(FIXTURE_PATH)
    state = State(cash_balance=1_000.0, risk_limits=RiskLimits(2.0, 0.8, 5_000.0))
    plan = [
        PlaceBuy(symbol="AAPL", quantity=1, price=0.0),
        PlaceBuy(symbol="AAPL", quantity=20, price=0.0),
    ]

    result = simulate_plan(state, plan, market_path)

    assert not result.approved
    assert result.rejected_step_index == 1
    assert len(result.trajectory) == 2
    assert any(error.code == "insufficient_cash" for error in result.steps[1].errors)


def test_simulator_uses_fixture_prices_deterministically():
    market_path = MarketPath.from_fixture(FIXTURE_PATH)
    state = State(cash_balance=10_000.0, risk_limits=RiskLimits(2.0, 0.6, 50_000.0))
    plan = [
        PlaceSell(symbol="AAPL", quantity=0, price=0.0),
    ]

    result = simulate_plan(state, plan, market_path)

    assert result.steps[0].price_context == market_path.price_context(0)
