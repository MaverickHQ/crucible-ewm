import json
import subprocess
from pathlib import Path


def test_demo_local_tape_outputs(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)

    result = subprocess.run(
        ["python3", "scripts/demo_local_trade_tape.py", "--steps", "5"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "run_id" in result.stdout
    assert "artifact_dir" in result.stdout

    tape_path = repo_root / "tmp" / "demo_local_tape" / "tape.json"
    report_path = repo_root / "tmp" / "demo_local_tape" / "report.md"
    csv_path = repo_root / "tmp" / "demo_local_tape" / "tape.csv"

    assert tape_path.exists()
    assert report_path.exists()
    assert csv_path.exists()

    payload = json.loads(tape_path.read_text())
    assert payload
    decisions = {row["decision"] for row in payload}
    assert decisions - {"HOLD"}

    multi_action_rows = [row for row in payload if len(row.get("actions", [])) > 1]
    if multi_action_rows:
        delta = multi_action_rows[0]["state_delta"]
        positions = delta.get("positions", {})
        assert "AAPL" in positions
        assert "MSFT" in positions
        assert abs(delta["cash"]["delta"]) > 0
        assert "exposure" in result.stdout

    report_text = report_path.read_text()
    assert "Trade Tape Report" in report_text
    assert "Replay" in report_text
    assert "Rejected steps" in report_text
    assert "Approved steps" in report_text

    replay = subprocess.run(
        ["python3", "scripts/replay_tape.py", "--tape", str(tape_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "step | prices | signals" in replay.stdout
    assert "run_id" in replay.stdout
    assert "artifact_dir" in replay.stdout
    assert any(token in replay.stdout for token in ["APPROVED", "REJECTED", "HOLD"])

    hold_rows = [line for line in result.stdout.splitlines() if " | HOLD |" in line]
    if hold_rows:
        assert " | - | " in hold_rows[0]
