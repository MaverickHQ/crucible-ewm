from services.core.broker.paper import LocalPaperBroker
from services.core.broker.types import OrderRequest
from services.core.state import RiskLimits, State


def test_paper_broker_deterministic_events() -> None:
    broker = LocalPaperBroker()
    orders = [
        OrderRequest(
            run_id="run-1",
            step_index=2,
            action_index=0,
            symbol="AAPL",
            side="BUY",
            quantity=1.0,
            limit_price=99.0,
        ),
        OrderRequest(
            run_id="run-1",
            step_index=2,
            action_index=1,
            symbol="MSFT",
            side="SELL",
            quantity=2.0,
            limit_price=200.0,
        ),
    ]

    events = broker.execute(orders, {"AAPL": 101.0, "MSFT": 199.5})
    assert events[0].event_id == "run-1:2:0"
    assert events[0].price == 101.0
    assert events[1].event_id == "run-1:2:1"
    assert events[1].price == 199.5


def test_paper_broker_records_exposure() -> None:
    broker = LocalPaperBroker()
    state = State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    orders = [
        OrderRequest(
            run_id="run-2",
            step_index=1,
            action_index=0,
            symbol="AAPL",
            side="BUY",
            quantity=1.0,
            limit_price=100.0,
        )
    ]

    events = broker.execute(orders, {"AAPL": 100.0}, starting_state=state)

    assert events[0].exposure_before == 0.0
    assert events[0].exposure_after == 100.0


def test_paper_broker_exposure_is_portfolio_based() -> None:
    broker = LocalPaperBroker()
    state = State(
        cash_balance=1_000.0,
        positions={"AAPL": 1.0},
        exposure=100.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    orders = [
        OrderRequest(
            run_id="run-3",
            step_index=1,
            action_index=0,
            symbol="AAPL",
            side="BUY",
            quantity=1.0,
            limit_price=100.0,
        ),
        OrderRequest(
            run_id="run-3",
            step_index=1,
            action_index=1,
            symbol="MSFT",
            side="BUY",
            quantity=1.0,
            limit_price=200.0,
        ),
    ]

    events = broker.execute(orders, {"AAPL": 100.0, "MSFT": 200.0}, starting_state=state)

    assert events[0].exposure_before == 100.0
    assert events[0].exposure_after == 200.0
    assert events[1].exposure_before == 200.0
    assert events[1].exposure_after == 400.0
