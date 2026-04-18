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


def call(url: str, payload: dict[str, Any], ca: str) -> dict[str, Any]:
    r = requests.post(url, json=payload, timeout=30, verify=ca)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    body["_http_status"] = r.status_code
    return body


def main() -> None:
    api = os.environ.get("AGENTCORE_LOOP_API_URL") or _stack_output("AgentCoreLoopApiUrl") or _stack_output("AgentCoreHelloApiUrl")
    if not api:
        raise SystemExit("Could not resolve AgentCoreLoopApiUrl from env or CloudFormation outputs.")

    url = api.rstrip("/") + "/agentcore/loop"
    ca = os.environ.get("REQUESTS_CA_BUNDLE") or certifi.where()

    print("AgentCore Loop Demo (no LLM)")
    print(f"Target API: {url}")
    print(f"TLS CA bundle: {ca}")

    ok_payload: dict[str, Any] = {
        "mode": "agentcore-loop",
        "seed": 7,
        "symbols": ["AAPL", "MSFT"],
        "starting_cash": 1000.0,
        "steps": 8,
        "write_artifacts": True,
        "budgets": {"max_steps": 8, "max_tool_calls": 200, "max_model_calls": 0, "max_memory_ops": 0, "max_memory_bytes": 0},
    }

    bad_payload = dict(ok_payload)
    bad_payload["budgets"] = dict(ok_payload["budgets"])
    bad_payload["budgets"]["max_model_calls"] = 1

    print("\n== loop ok (expect ok=true) ==")
    out1 = call(url, ok_payload, ca)
    print(json.dumps(out1, indent=2))

    print("\n== invalid_budget (expect ok=false) ==")
    out2 = call(url, bad_payload, ca)
    print(json.dumps(out2, indent=2))

    assert out1.get("ok") is True
    assert out2.get("ok") is False


if __name__ == "__main__":
    main()
