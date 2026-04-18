from ewm_core.actions import PlaceBuy
from ewm_core.loop.formatting import render_execution_row
from ewm_core.loop.run import _execution_rows_for_actions
from ewm_core.loop.types import ExecutionRow
from ewm_core.state import RiskLimits, State


def test_execution_row_formatting() -> None:
    row = ExecutionRow(
        step_index=1,
        run_id="run-1",
        decision="APPROVED",
        symbol="AAPL",
        side="BUY",
        quantity=1.0,
        price=100.0,
        cash_before=1_000.0,
        cash_after=900.0,
        exposure_before=0.0,
        exposure_after=100.0,
        positions_before={"AAPL": 0.0},
        positions_after={"AAPL": 1.0},
        reason="AAPL: price < buy_below",
        verification="verified OK",
    )

    rendered = render_execution_row(row)
    assert "1 | AAPL | BUY" in rendered
    assert "1000.00" in rendered
    assert "900.00" in rendered
    assert "0.00" in rendered
    assert "100.00" in rendered
    assert "AAPL 0.00" in rendered
    assert "AAPL 1.00" in rendered


def test_execution_rows_are_sequential() -> None:
    prior_state = State(
        cash_balance=1_000.0,
        positions={"AAPL": 0.0, "MSFT": 0.0},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    actions = [
        PlaceBuy(symbol="AAPL", quantity=1.0, price=100.0),
        PlaceBuy(symbol="MSFT", quantity=1.0, price=200.0),
    ]
    next_state = State(
        cash_balance=700.0,
        positions={"AAPL": 1.0, "MSFT": 1.0},
        exposure=300.0,
        risk_limits=prior_state.risk_limits,
    )

    rows = _execution_rows_for_actions(
        step_index=1,
        run_id="run-1",
        decision="APPROVED",
        actions=actions,
        prices={"AAPL": 100.0, "MSFT": 200.0},
        prior_state=prior_state,
        next_state=next_state,
        reason="AAPL: price < buy_below; MSFT: price < buy_below",
        verification="verified OK",
    )

    assert len(rows) == 2
    assert rows[0].cash_before == 1_000.0
    assert rows[0].cash_after == 900.0
    assert rows[1].cash_before == 900.0
    assert rows[1].cash_after == 700.0
    assert rows[0].exposure_before == 0.0
    assert rows[0].exposure_after == 100.0
    assert rows[1].exposure_before == 100.0
    assert rows[1].exposure_after == 300.0
    assert rows[0].positions_before == {"AAPL": 0.0}
    assert rows[0].positions_after == {"AAPL": 1.0}
    assert rows[1].positions_before == {"MSFT": 0.0}
    assert rows[1].positions_after == {"MSFT": 1.0}
    assert rows[0].reason.startswith("AAPL:")
    assert rows[1].reason.startswith("MSFT:")
