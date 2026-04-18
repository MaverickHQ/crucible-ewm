import os
import subprocess

import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_AWS_TESTS") != "1",
    reason="RUN_AWS_TESTS not enabled",
)
def test_agentcore_tools_smoke():
    result = subprocess.run(
        ["python3", "scripts/smoke_agentcore_tools.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"ok": true' in result.stdout.lower()
