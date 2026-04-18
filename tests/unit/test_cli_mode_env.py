from __future__ import annotations

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


def test_target_show_and_set_persists(tmp_path) -> None:
    home = str(tmp_path)

    show = _run(["target", "show"], home)
    assert show.returncode == 0
    assert show.stdout.strip() == "target: local"

    set_target = _run(["target", "set", "aws"], home)
    assert set_target.returncode == 0
    assert set_target.stdout.strip() == "aws"

    show_after = _run(["target", "show"], home)
    assert show_after.returncode == 0
    assert show_after.stdout.strip() == "target: aws"


def test_mode_show_and_set_persists(tmp_path) -> None:
    home = str(tmp_path)

    show = _run(["mode", "show"], home)
    assert show.returncode == 0
    assert show.stdout.strip() == "mode: local"

    set_mode = _run(["mode", "set", "aws"], home)
    assert set_mode.returncode == 0
    assert set_mode.stdout.strip() == "aws"

    show_after = _run(["mode", "show"], home)
    assert show_after.returncode == 0
    assert show_after.stdout.strip() == "mode: aws"


def test_env_show_and_set_persists(tmp_path) -> None:
    home = str(tmp_path)

    show = _run(["env", "show"], home)
    assert show.returncode == 0
    assert show.stdout.strip() == "env: paper"

    set_env = _run(["env", "set", "prod"], home)
    assert set_env.returncode == 0
    assert set_env.stdout.strip() == "prod"

    show_after = _run(["env", "show"], home)
    assert show_after.returncode == 0
    assert show_after.stdout.strip() == "env: prod"


def test_invalid_mode_and_env_return_nonzero(tmp_path) -> None:
    home = str(tmp_path)

    bad_mode = _run(["mode", "set", "invalid"], home)
    assert bad_mode.returncode != 0

    bad_env = _run(["env", "set", "invalid"], home)
    assert bad_env.returncode != 0


def test_show_raw_outputs_are_unlabeled(tmp_path) -> None:
    home = str(tmp_path)

    target_show = _run(["target", "show", "--raw"], home)
    assert target_show.returncode == 0
    assert target_show.stdout.strip() == "local"

    mode_show = _run(["mode", "show", "--raw"], home)
    assert mode_show.returncode == 0
    assert mode_show.stdout.strip() == "local"

    env_show = _run(["env", "show", "--raw"], home)
    assert env_show.returncode == 0
    assert env_show.stdout.strip() == "paper"
