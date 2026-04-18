import json
import subprocess


def test_replay_executions_includes_events(tmp_path) -> None:
    payload = {
        "executions": [
            {
                "step_index": 1,
                "run_id": "run-1",
                "artifact_dir": "tmp/artifacts/run-1",
                "events": [
                    {
                        "event_id": "run-1:1:0",
                        "run_id": "run-1",
                        "step_index": 1,
                        "action_index": 0,
                        "symbol": "AAPL",
                        "side": "BUY",
                        "quantity": 1.0,
                        "price": 100.0,
                        "status": "FILLED",
                        "cash_before": 1000.0,
                        "cash_after": 900.0,
                        "positions_before": {"AAPL": 0.0},
                        "positions_after": {"AAPL": 1.0},
                        "exposure_before": 0.0,
                        "exposure_after": 100.0,
                        "why": "paper fill",
                    }
                ],
                "ledger_rows": [
                    {
                        "step_index": 1,
                        "run_id": "run-1",
                        "decision": "APPROVED",
                        "symbol": "AAPL",
                        "side": "BUY",
                        "quantity": 1.0,
                        "price": 100.0,
                        "cash_before": 1000.0,
                        "cash_after": 900.0,
                        "exposure_before": 0.0,
                        "exposure_after": 100.0,
                        "positions_before": {"AAPL": 0.0},
                        "positions_after": {"AAPL": 1.0},
                        "reason": "AAPL: test",
                        "verification": "verified OK",
                    }
                ],
            }
        ]
    }

    path = tmp_path / "executions.json"
    path.write_text(json.dumps(payload))

    result = subprocess.run(
        ["python3", "scripts/replay_executions.py", "--executions", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Execution Events" in result.stdout
    assert "Execution Ledger" in result.stdout
