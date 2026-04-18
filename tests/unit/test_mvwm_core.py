from services.core.actions import PlaceBuy, PlaceSell
from services.core.state import RiskLimits, State
from services.core.transitions import apply_action
from services.core.verifier import verify_transition


def test_valid_buy_transition():
    state = State(cash_balance=10_000.0, risk_limits=RiskLimits(2.0, 0.6, 50_000.0))
    action = PlaceBuy(symbol="AAPL", quantity=10, price=100.0)

    verification = verify_transition(state, action)
    assert verification.accepted

    result = apply_action(state, action)
    assert result.next_state.positions["AAPL"] == 10
    assert result.next_state.cash_balance == 9_000.0


def test_invalid_buy_rejected_with_reason():
    state = State(cash_balance=100.0, risk_limits=RiskLimits(1.0, 0.5, 1_000.0))
    action = PlaceBuy(symbol="AAPL", quantity=10, price=100.0)

    verification = verify_transition(state, action)
    assert not verification.accepted
    assert any(error.code == "insufficient_cash" for error in verification.errors)


def test_invariants_preserved_on_sell():
    state = State(
        cash_balance=1_000.0,
        positions={"AAPL": 5},
        exposure=500.0,
        risk_limits=RiskLimits(2.0, 0.6, 50_000.0),
    )
    action = PlaceSell(symbol="AAPL", quantity=2, price=100.0)

    verification = verify_transition(state, action)
    assert verification.accepted

    result = apply_action(state, action)
    assert result.next_state.cash_balance == 1_200.0
    assert result.next_state.positions["AAPL"] == 3
