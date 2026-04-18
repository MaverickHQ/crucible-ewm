from ewm_core.observability import TapeRow


def test_tape_row_schema() -> None:
    row = TapeRow(
        step_index=0,
        prices={"AAPL": 100.0},
        signals={"AAPL": "BUY"},
        rationales={"AAPL": "price < buy_below"},
        actions=[{"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1.0, "price": 100.0}],
        decision="APPROVED",
        why="AAPL: price < buy_below | verified OK",
        explanation="Accepted",
        state_delta={},
        verifier_errors=[],
        run_id="run-1",
        artifact_dir="/tmp",
    )

    payload = row.to_dict()
    expected_keys = {
        "step_index",
        "prices",
        "signals",
        "rationales",
        "actions",
        "decision",
        "why",
        "explanation",
        "state_delta",
        "verifier_errors",
        "run_id",
        "artifact_dir",
    }

    assert set(payload.keys()) == expected_keys
