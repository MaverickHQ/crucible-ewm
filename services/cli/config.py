from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

VALID_TARGETS = {"local", "aws", "both"}
VALID_MODES = VALID_TARGETS
VALID_ENVS = {"paper", "prod"}
VALID_COST_PROFILES = {"integration", "paper", "prod"}

COST_PROFILE_DEFAULTS: dict[str, dict[str, int]] = {
    "integration": {
        "steps": 5,
        "tool_calls": 50,
        "model_calls": 0,
        "memory_ops": 20,
        "memory_bytes": 64_000,
    },
    "paper": {
        "steps": 20,
        "tool_calls": 200,
        "model_calls": 0,
        "memory_ops": 200,
        "memory_bytes": 512_000,
    },
    "prod": {
        "steps": 10,
        "tool_calls": 100,
        "model_calls": 0,
        "memory_ops": 100,
        "memory_bytes": 256_000,
    },
}


def _home_dir() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def config_dir() -> Path:
    return _home_dir() / ".ewm"


def config_path() -> Path:
    return config_dir() / "config.json"


def default_config() -> dict[str, Any]:
    return {
        "target": "local",
        "mode": "local",
        "env": "paper",
        "cost_profile": "integration",
        "budgets": dict(COST_PROFILE_DEFAULTS["integration"]),
    }


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    target = normalized.get("target")
    mode = normalized.get("mode")
    if target is None and mode in VALID_MODES:
        target = mode
    if target is None:
        target = "local"
    normalized["target"] = target
    normalized["mode"] = target  # backwards-compatible mirror

    if normalized.get("env") is None:
        normalized["env"] = "paper"

    profile = normalized.get("cost_profile") or "integration"
    normalized["cost_profile"] = profile

    budgets = normalized.get("budgets")
    if not isinstance(budgets, dict):
        budgets = dict(COST_PROFILE_DEFAULTS.get(profile, COST_PROFILE_DEFAULTS["integration"]))
    normalized["budgets"] = budgets

    return normalized


def _validate_config(data: dict[str, Any]) -> None:
    target = data.get("target")
    env = data.get("env")
    profile = data.get("cost_profile")
    budgets = data.get("budgets")

    if target not in VALID_TARGETS:
        raise ValueError(f"invalid target: {target}")
    if env not in VALID_ENVS:
        raise ValueError(f"invalid env: {env}")
    if profile not in VALID_COST_PROFILES:
        raise ValueError(f"invalid cost_profile: {profile}")
    if not isinstance(budgets, dict):
        raise ValueError("invalid budgets: must be an object")
    for key, value in budgets.items():
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid budget {key}: must be non-negative integer")


def write_config(data: dict[str, Any]) -> Path:
    normalized = _normalize_config(data)
    _validate_config(normalized)
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as tmp:
        json.dump(normalized, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    tmp_path.replace(target)
    return target


def ensure_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        data = default_config()
        write_config(data)
        return data

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")
    normalized = _normalize_config(raw)
    _validate_config(normalized)
    if normalized != raw:
        write_config(normalized)
    return normalized


def resolve_target(cfg: dict[str, Any]) -> str:
    target = cfg.get("target")
    if target in VALID_TARGETS:
        return str(target)
    mode = cfg.get("mode")
    if mode in VALID_MODES:
        return str(mode)
    return "local"
