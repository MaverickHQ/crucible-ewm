from __future__ import annotations

import json

from services.cli.config import config_path, ensure_config, write_config


def test_ensure_config_creates_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg = ensure_config()
    assert cfg["mode"] == "local"
    assert cfg["target"] == "local"
    assert cfg["env"] == "paper"
    assert cfg["cost_profile"] == "integration"
    assert isinstance(cfg["budgets"], dict)

    path = config_path()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mode"] == "local"
    assert data["target"] == "local"
    assert data["env"] == "paper"


def test_write_config_persists_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    write_config({"mode": "aws", "env": "prod"})
    cfg = ensure_config()
    assert cfg["mode"] == "aws"
    assert cfg["target"] == "aws"
    assert cfg["env"] == "prod"
    assert cfg["cost_profile"] == "integration"


def test_invalid_config_exits_nonzero(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": "oops", "env": "paper"}), encoding="utf-8")

    cfg = ensure_config()
    assert cfg["target"] == "local"
    assert cfg["mode"] == "local"
    assert cfg["env"] == "paper"
