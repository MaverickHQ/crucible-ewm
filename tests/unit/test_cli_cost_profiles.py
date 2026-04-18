from __future__ import annotations

import json
import os
import subprocess
import sys


def _run(args: list[str], home: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = home
    return subprocess.run(
        [sys.executable, "-m", "services.cli.main", *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_cost_show_defaults(tmp_path) -> None:
    home = str(tmp_path)
    result = _run(["cost", "show"], home)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["cost_profile"] == "integration"
    assert payload["budgets"]["steps"] == 5


def test_cost_set_and_apply_integration(tmp_path) -> None:
    home = str(tmp_path)

    set_result = _run(["cost", "set", "--profile", "integration", "--steps", "9"], home)
    assert set_result.returncode == 0

    apply_result = _run(["cost", "apply"], home)
    assert apply_result.returncode == 0
    payload = json.loads(apply_result.stdout)
    assert payload["cost_profile"] == "integration"
    assert payload["budgets"]["steps"] == 9


def test_prod_apply_requires_yes(tmp_path) -> None:
    home = str(tmp_path)
    set_result = _run(["cost", "set", "--profile", "prod"], home)
    assert set_result.returncode == 0

    apply_fail = _run(["cost", "apply"], home)
    assert apply_fail.returncode != 0

    apply_ok = _run(["cost", "apply", "--yes"], home)
    assert apply_ok.returncode == 0
    assert "WARNING: applying PROD cost profile" in apply_ok.stdout
