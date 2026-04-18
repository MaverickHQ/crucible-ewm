from services.core.actions import PlaceBuy
from services.core.explain import explain_transition
from services.core.state import RiskLimits, State
from services.core.transitions import apply_action
from services.core.verifier import verify_transition


def test_explain_transition_accepts_includes_deltas():
    state = State(cash_balance=1_000.0, risk_limits=RiskLimits(2.0, 0.8, 5_000.0))
    action = PlaceBuy("AAPL", 1, 100.0)

    verification = verify_transition(state, action)
    transition = apply_action(state, action)
    explanation = explain_transition(
        state,
        action,
        transition.next_state,
        verification,
        transition.prices,
    )

    assert explanation.startswith("Accepted:")
    assert "cash" in explanation
    assert "exposure" in explanation


def test_explain_transition_rejects_with_reason():
    state = State(cash_balance=10.0, risk_limits=RiskLimits(1.0, 0.5, 1_000.0))
    action = PlaceBuy("AAPL", 1, 100.0)

    verification = verify_transition(state, action)
    explanation = explain_transition(state, action, state, verification, {"AAPL": 100.0})

    assert explanation.startswith("Rejected:")
    assert "insufficient_cash" in explanation
