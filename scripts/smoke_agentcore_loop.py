from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import certifi
import requests


def _stack_output(key: str) -> str | None:
    try:
        out = subprocess.check_output(
            [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                "BeyondTokensStack",
                "--query",
                f"Stacks[0].Outputs[?OutputKey=='{key}'].OutputValue | [0]",
                "--output",
                "text",
            ],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return out if out and out != "None" else None
    except Exception:
        return None


def main() -> None:
    api = (
        os.environ.get("AGENTCORE_LOOP_API_URL")
        or _stack_output("AgentCoreLoopApiUrl")
        or _stack_output("AgentCoreHelloApiUrl")
    )
    if not api:
        raise SystemExit("Could not resolve AgentCoreLoopApiUrl from env or CloudFormation outputs.")

    url = api.rstrip("/") + "/agentcore/loop"
    ca = os.environ.get("REQUESTS_CA_BUNDLE") or certifi.where()

    payload: dict[str, Any] = {
        "mode": "agentcore-loop",
        "seed": 7,
        "symbols": ["AAPL", "MSFT"],
        "starting_cash": 1000.0,
        "steps": 5,
        "write_artifacts": True,
        "budgets": {
            "max_steps": 5,
            "max_tool_calls": 50,
            "max_model_calls": 0,
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        },
    }

    r = requests.post(url, json=payload, timeout=30, verify=ca)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    print(json.dumps({"http_status": r.status_code, "body": body}, indent=2))
    if r.status_code != 200:
        raise SystemExit(f"HTTP {r.status_code}")
    if body.get("ok") is not True:
        raise SystemExit("Expected ok=true in response")


if __name__ == "__main__":
    main()