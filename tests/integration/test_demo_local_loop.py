import json
import subprocess
from pathlib import Path


def test_demo_local_loop_outputs(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)

    result = subprocess.run(
        ["python3", "scripts/demo_local_loop.py", "--steps", "5"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Execution Ledger" in result.stdout
    assert "step | prices | signals" in result.stdout
    assert "step | symbol | side" in result.stdout
    assert "exposure" in result.stdout

    data_dir = repo_root / "tmp" / "demo_local_loop"
    tape_path = data_dir / "tape.json"
    executions_path = data_dir / "executions.json"
    report_path = data_dir / "report.md"

    assert tape_path.exists()
    assert executions_path.exists()
    assert report_path.exists()

    payload = json.loads(tape_path.read_text())
    executions_payload = json.loads(executions_path.read_text())
    if isinstance(executions_payload, dict):
        executions = [
            row
            for bundle in executions_payload.get("executions", [])
            for row in bundle.get("ledger_rows", [])
        ]
        event_rows = [
            event
            for bundle in executions_payload.get("executions", [])
            for event in bundle.get("events", [])
        ]
    else:
        executions = executions_payload
        event_rows = []

    assert payload
    assert any(row["decision"] == "APPROVED" for row in payload)
    assert all(row["decision"] == "APPROVED" for row in executions)

    multi_action_steps = [
        row["step_index"]
        for row in payload
        if row["decision"] == "APPROVED" and len(row.get("actions", [])) > 1
    ]
    if multi_action_steps:
        step_index = multi_action_steps[0]
        step_rows = [row for row in executions if row["step_index"] == step_index]
        assert len(step_rows) > 1
        assert step_rows[1]["cash_before"] == step_rows[0]["cash_after"]
        assert step_rows[1]["exposure_before"] == step_rows[0]["exposure_after"]
        assert step_rows[1]["exposure_after"] > step_rows[0]["exposure_after"]
        for row in step_rows:
            symbol = row["symbol"]
            if f"{symbol}:" in row["reason"]:
                assert row["reason"].startswith(f"{symbol}:")

    replay_tape = subprocess.run(
        ["python3", "scripts/replay_tape.py", "--tape", str(tape_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "step | prices | signals" in replay_tape.stdout
    assert "exposure" in replay_tape.stdout

    replay_executions = subprocess.run(
        [
            "python3",
            "scripts/replay_executions.py",
            "--executions",
            str(executions_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Execution Ledger" in replay_executions.stdout
    assert "exposure" in replay_executions.stdout
    if event_rows:
        assert "Execution Events" in replay_executions.stdout
