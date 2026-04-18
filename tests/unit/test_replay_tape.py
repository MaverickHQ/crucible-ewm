import json
import subprocess


def test_replay_tape_script_outputs(tmp_path) -> None:
    tape_path = tmp_path / "tape.json"
    tape_path.write_text(
        json.dumps(
            [
                {
                    "step_index": 0,
                    "prices": {"AAPL": 100.0},
                    "signals": {"AAPL": "BUY"},
                    "rationales": {"AAPL": "price < buy_below"},
                    "actions": [
                        {
                            "type": "PlaceBuy",
                            "symbol": "AAPL",
                            "quantity": 1.0,
                            "price": 100.0,
                        }
                    ],
                    "decision": "APPROVED",
                    "why": "AAPL: price < buy_below | verified OK",
                    "explanation": "Accepted",
                    "state_delta": {
                        "cash": {"delta": -100.0},
                        "exposure": {"delta": 100.0},
                        "positions": {"AAPL": {"delta": 1.0}},
                    },
                    "verifier_errors": [],
                    "run_id": "run-1",
                    "artifact_dir": "/tmp/demo",
                }
            ]
        )
    )

    result = subprocess.run(
        ["python3", "scripts/replay_tape.py", "--tape", str(tape_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "step | prices | signals" in result.stdout
    assert "exposure +100.00" in result.stdout
    assert "APPROVED" in result.stdout
