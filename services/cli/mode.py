from __future__ import annotations

from services.cli.config import (
    VALID_ENVS,
    VALID_TARGETS,
    ensure_config,
    resolve_target,
    write_config,
)


def show_target(raw: bool = False) -> str:
    value = resolve_target(ensure_config())
    if raw:
        return value
    return f"target: {value}"


def set_target(value: str) -> str:
    if value not in VALID_TARGETS:
        raise ValueError(f"invalid target: {value}")
    cfg = ensure_config()
    cfg["target"] = value
    cfg["mode"] = value  # backward compatibility
    write_config(cfg)
    return value


def show_mode(raw: bool = False) -> str:
    value = resolve_target(ensure_config())
    if raw:
        return value
    return f"mode: {value}"


def set_mode(value: str) -> str:
    return set_target(value)


def show_env(raw: bool = False) -> str:
    value = str(ensure_config()["env"])
    if raw:
        return value
    return f"env: {value}"


def set_env(value: str) -> str:
    if value not in VALID_ENVS:
        raise ValueError(f"invalid env: {value}")
    cfg = ensure_config()
    cfg["env"] = value
    write_config(cfg)
    return value
