from services.core.deltas import compute_state_delta
from services.core.state import RiskLimits, State


def test_compute_state_delta_for_buy():
    prior = State(
        cash_balance=1_000.0,
        positions={"AAPL": 0.0},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    next_state = State(
        cash_balance=900.0,
        positions={"AAPL": 1.0},
        exposure=100.0,
        risk_limits=prior.risk_limits,
    )

    delta = compute_state_delta(prior, next_state, {"AAPL": 100.0})

    assert delta["cash"]["delta"] == -100.0
    assert delta["positions"]["AAPL"]["delta"] == 1.0
    assert delta["exposure"]["after"] == 100.0


def test_compute_state_delta_for_sell():
    prior = State(
        cash_balance=1_000.0,
        positions={"AAPL": 2.0},
        exposure=200.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    next_state = State(
        cash_balance=1_200.0,
        positions={"AAPL": 1.0},
        exposure=100.0,
        risk_limits=prior.risk_limits,
    )

    delta = compute_state_delta(prior, next_state, {"AAPL": 100.0})

    assert delta["cash"]["delta"] == 200.0
    assert delta["positions"]["AAPL"]["delta"] == -1.0
    assert delta["exposure"]["after"] == 100.0


def test_compute_state_delta_for_multi_action_net():
    prior = State(
        cash_balance=1_000.0,
        positions={"AAPL": 0.0, "MSFT": 0.0},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    next_state = State(
        cash_balance=700.0,
        positions={"AAPL": 1.0, "MSFT": 1.0},
        exposure=300.0,
        risk_limits=prior.risk_limits,
    )

    delta = compute_state_delta(prior, next_state, {"AAPL": 100.0, "MSFT": 200.0})

    assert delta["cash"]["delta"] == -300.0
    assert delta["exposure"]["delta"] == 300.0
    assert delta["positions"]["AAPL"]["delta"] == 1.0
    assert delta["positions"]["MSFT"]["delta"] == 1.0
