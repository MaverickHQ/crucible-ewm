import os
import subprocess

import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_AWS_TESTS") != "1" or os.environ.get("ENABLE_AGENTCORE_MEMORY") != "1",
    reason="RUN_AWS_TESTS or ENABLE_AGENTCORE_MEMORY not enabled",
)
def test_agentcore_memory_smoke():
    result = subprocess.run(
        ["python3", "scripts/smoke_agentcore_memory.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"ok": true' in result.stdout.lower()
    assert '"value": "hello"' in result.stdout.lower()
