from __future__ import annotations

from typing import Any

from services.cli.config import (
    COST_PROFILE_DEFAULTS,
    VALID_COST_PROFILES,
    ensure_config,
    write_config,
)

BUDGET_KEYS = ["steps", "tool_calls", "model_calls", "memory_ops", "memory_bytes"]


def show_cost() -> dict[str, Any]:
    cfg = ensure_config()
    return {
        "cost_profile": cfg["cost_profile"],
        "budgets": dict(cfg["budgets"]),
    }


def set_cost_profile(
    profile: str,
    *,
    steps: int | None = None,
    tool_calls: int | None = None,
    model_calls: int | None = None,
    memory_ops: int | None = None,
    memory_bytes: int | None = None,
) -> dict[str, Any]:
    if profile not in VALID_COST_PROFILES:
        raise ValueError(f"invalid cost profile: {profile}")

    overrides = {
        "steps": steps,
        "tool_calls": tool_calls,
        "model_calls": model_calls,
        "memory_ops": memory_ops,
        "memory_bytes": memory_bytes,
    }
    for key, value in overrides.items():
        if value is not None and value < 0:
            raise ValueError(f"invalid {key}: must be non-negative")

    cfg = ensure_config()
    pending = cfg.setdefault("pending_cost", {})
    pending["cost_profile"] = profile
    budgets = dict(COST_PROFILE_DEFAULTS[profile])
    for key in BUDGET_KEYS:
        val = overrides[key]
        if val is not None:
            budgets[key] = int(val)
    pending["budgets"] = budgets
    write_config(cfg)
    return {"pending_cost": pending}


def apply_cost(*, yes: bool = False) -> dict[str, Any]:
    cfg = ensure_config()
    pending = cfg.get("pending_cost")
    if not isinstance(pending, dict):
        raise ValueError("no pending cost profile; run `ewm cost set` first")

    profile = pending.get("cost_profile")
    if profile not in VALID_COST_PROFILES:
        raise ValueError(f"invalid pending cost profile: {profile}")
    if profile == "prod" and not yes:
        raise ValueError("prod profile requires --yes")

    budgets = pending.get("budgets")
    if not isinstance(budgets, dict):
        raise ValueError("invalid pending budgets")

    cfg["cost_profile"] = profile
    cfg["budgets"] = budgets
    cfg.pop("pending_cost", None)
    write_config(cfg)
    return {"cost_profile": profile, "budgets": budgets}
