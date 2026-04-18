from __future__ import annotations

import os
from pathlib import Path

from services.cli.config import config_path, ensure_config, resolve_target


def _detect_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return None


def run_check(cwd: Path | None = None) -> int:
    cfg = ensure_config()
    path = config_path()
    print(f"config_path: {path}")
    target = resolve_target(cfg)
    print(f"target: {target}")
    print(f"mode: {cfg['mode']}")
    print(f"env: {cfg['env']}")
    print(f"cost_profile: {cfg['cost_profile']}")
    print(f"budgets: {cfg['budgets']}")

    for key, value in cfg["budgets"].items():
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid budget {key}: must be non-negative integer")

    repo_root = _detect_repo_root(cwd or Path.cwd())
    if repo_root is not None:
        print(f"repo_root: {repo_root}")
    else:
        print("repo_root: not detected")

    if target in {"aws", "both"}:
        has_profile = bool(os.environ.get("AWS_PROFILE"))
        has_region = bool(os.environ.get("AWS_REGION"))
        print(f"aws_env.AWS_PROFILE: {'set' if has_profile else 'missing'}")
        print(f"aws_env.AWS_REGION: {'set' if has_region else 'missing'}")
        if not has_profile or not has_region:
            raise ValueError("aws target requires AWS_PROFILE and AWS_REGION")

    return 0
