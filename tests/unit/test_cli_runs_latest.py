from __future__ import annotations

import json

from services.cli import runs


def test_runs_latest_no_data_prints_help(monkeypatch, capsys, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)

    rc = runs.runs_latest()
    out = capsys.readouterr().out
    assert rc == 0
    assert "No local runs found. Run scripts/demo_local_loop.py first." in out


def test_runs_latest_reads_runs_and_plan_summary(monkeypatch, capsys, tmp_path) -> None:
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [
        {
            "run_id": "r-1",
            "ok": True,
            "plan": {
                "meta": {"planner": "local"},
                "steps": [{"tool": "validate_request"}, {"tool": "run_loop"}],
            },
        }
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    assert "source:" in out
    assert "run_id: r-1" in out
    assert "approved: None" in out
    assert "steps: 0" in out
    assert "positions: none" in out
    assert "plan: present (2 steps)" in out


def test_runs_latest_raw_and_json_output(monkeypatch, capsys, tmp_path) -> None:
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [{"run_id": "r-raw", "approved": True, "steps": [{"tool": "x"}]}]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)

    rc_raw = runs.runs_latest(raw=True)
    out_raw = capsys.readouterr().out
    assert rc_raw == 0
    assert out_raw.strip().startswith("{")
    assert '"run_id": "r-raw"' in out_raw

    rc_json = runs.runs_latest(json_output=True)
    out_json = capsys.readouterr().out
    assert rc_json == 0
    assert out_json.strip().startswith("{")
    assert '\n  "approved": true' in out_json


def test_runs_latest_default_summary_includes_final_state(monkeypatch, capsys, tmp_path) -> None:
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [
        {
            "run_id": "r-final",
            "approved": False,
            "steps": [{"tool": "a"}, {"tool": "b"}],
            "trajectory": [
                {"cash_balance": 1000, "exposure": 0.1, "positions": {"AAPL": 1}},
                {"cash_balance": 900, "exposure": 0.2, "positions": {"AAPL": 2, "MSFT": 1}},
            ],
            "plan": {"steps": [{"tool": "validate_request"}]},
        }
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)

    rc = runs.runs_latest()
    out = capsys.readouterr().out
    assert rc == 0
    assert "run_id: r-final" in out
    assert "approved: False" in out
    assert "steps: 2" in out
    assert "final_cash: 900.00" in out
    assert "final_exposure: 0.20" in out
    assert "positions:" in out and "AAPL=2" in out and "MSFT=1" in out
    assert "plan: present (1 steps)" in out


def test_runs_tail_respects_n(monkeypatch, capsys, tmp_path) -> None:
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [{"run_id": f"r-{i}"} for i in range(5)]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_tail(2)
    out = capsys.readouterr().out

    assert rc == 0
    assert '"run_id": "r-4"' in out
    assert '"run_id": "r-3"' in out
    assert '"run_id": "r-1"' not in out


def test_extract_runs_handles_dict_of_runs(monkeypatch, capsys, tmp_path) -> None:
    """Test that {uuid: run_obj} format parses to list of runs."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    # Dict format: {run_id: run_data, ...}
    payload = {
        "r-1": {"run_id": "r-1", "approved": True, "steps": [{"tool": "a"}]},
        "r-2": {"run_id": "r-2", "approved": False, "steps": [{"tool": "b"}]},
    }
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    # Should pick last one as fallback (r-2)
    assert "run_id: r-2" in out


def test_extract_runs_rejects_non_run_dict(monkeypatch, capsys, tmp_path) -> None:
    """Test that dict-of-dicts that don't look like runs is not treated as runs."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    # This dict has dict values but they don't look like runs (no steps field)
    payload = {
        "key1": {"name": "foo", "value": 1},
        "key2": {"name": "bar", "value": 2},
    }
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    runs.runs_latest()
    out = capsys.readouterr().out

    # Should not find any runs
    assert "No local runs found" in out


def test_pick_latest_prefers_created_at(monkeypatch, capsys, tmp_path) -> None:
    """Test that latest selection prefers created_at when present."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    # Runs with created_at timestamps - last one in list is NOT latest by timestamp
    payload = [
        {"run_id": "r-oldest", "approved": True, "steps": [], "created_at": "2024-01-01T10:00:00Z"},
        {"run_id": "r-middle", "approved": True, "steps": [], "created_at": "2024-01-02T10:00:00Z"},
        {"run_id": "r-latest", "approved": True, "steps": [], "created_at": "2024-01-03T10:00:00Z"},
        # This is last in file but NOT latest by timestamp
        {"run_id": "r-last-file", "approved": True, "steps": []},
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    # Should pick r-latest (by created_at), not r-last-file (by position)
    assert "run_id: r-latest" in out


def test_rejection_summary_includes_fields(monkeypatch, capsys, tmp_path) -> None:
    """Test rejection summary includes rejected_step_index, action, and errors."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [
        {
            "run_id": "r-rejected",
            "approved": False,
            "rejected_step_index": 0,
            "steps": [
                {
                    "step_index": 0,
                    "accepted": False,
                    "action": {
                        "type": "PlaceBuy",
                        "symbol": "AAPL",
                        "quantity": 10.0,
                        "price": 150.0,
                    },
                    "errors": [{"code": "position_limit", "message": "Position limit exceeded"}],
                }
            ],
            "trajectory": [{"cash_balance": 1000, "exposure": 0, "positions": {}}],
        }
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    assert "approved: False" in out
    assert "rejected_step_index: 0" in out
    assert "rejected_action: PlaceBuy AAPL 10.0@150.0" in out
    assert "rejected_errors:" in out
    assert "position_limit" in out


def test_plan_none_wording(monkeypatch, capsys, tmp_path) -> None:
    """Test that plan: none has improved wording when no plan recorded."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    # Run without plan field
    payload = [
        {
            "run_id": "r-no-plan",
            "approved": True,
            "steps": [],
        }
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    assert "plan: none (no planner output recorded)" in out


def test_created_at_shown_in_summary(monkeypatch, capsys, tmp_path) -> None:
    """Test that created_at is shown when present in run."""
    repo = tmp_path / "repo"
    runs_dir = repo / "tmp" / "demo_local_loop"
    runs_dir.mkdir(parents=True)
    payload = [
        {
            "run_id": "r-with-time",
            "approved": True,
            "steps": [],
            "created_at": "2024-06-15T14:30:00Z",
        }
    ]
    (runs_dir / "runs.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(runs, "_repo_root", lambda _cwd=None: repo)
    rc = runs.runs_latest()
    out = capsys.readouterr().out

    assert rc == 0
    assert "created_at: 2024-06-15T14:30:00Z" in out
