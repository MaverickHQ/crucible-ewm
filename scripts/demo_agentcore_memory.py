from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
import certifi
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.aws.utils.output_loader import load_outputs

OUTPUTS_PATH = Path(
    os.environ.get("AWS_OUTPUTS_PATH", ROOT / "infra" / "cdk" / "cdk-outputs.json")
)


def _sanitize(payload: dict) -> dict:
    if "artifact_dir" in payload:
        payload = dict(payload)
        payload["artifact_dir"] = "s3://<redacted>/artifacts/<run_id>/"
    return payload


def _invoke_api(api_url: str, body: dict) -> dict:
    url = api_url.rstrip("/") + "/agentcore/memory"
    response = requests.post(
        url,
        json=body,
        headers={"content-type": "application/json"},
        timeout=10,
        verify=_ca_bundle_path(),
    )
    parsed = response.json()
    if isinstance(parsed, dict) and "body" in parsed:
        return json.loads(parsed["body"]) if isinstance(parsed["body"], str) else parsed["body"]
    return parsed


def _ca_bundle_path() -> str:
    return os.environ.get("REQUESTS_CA_BUNDLE") or certifi.where()


def _invoke_lambda(function_name: str, body: dict) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(body).encode("utf-8"),
    )
    return json.loads(response["Payload"].read().decode("utf-8"))


def _load_outputs() -> dict:
    if OUTPUTS_PATH.exists():
        return load_outputs(OUTPUTS_PATH)

    stack_name = os.environ.get("AWS_STACK_NAME", "BeyondTokensStack")
    client = boto3.client("cloudformation")
    response = client.describe_stacks(StackName=stack_name)
    stacks = response.get("Stacks", [])
    if not stacks:
        raise SystemExit("Missing stack outputs; deploy the stack first.")

    outputs = {}
    for output in stacks[0].get("Outputs", []):
        outputs[output["OutputKey"]] = output["OutputValue"]
    return outputs


def _run(api_url: str | None, function_name: str | None, body: dict) -> dict:
    if api_url:
        try:
            return _invoke_api(api_url, body)
        except requests.RequestException as exc:
            if os.environ.get("ALLOW_LAMBDA_FALLBACK") == "1" and function_name:
                print(f"API invoke failed; falling back to lambda invoke: {exc}")
                return _invoke_lambda(function_name, body)
            raise
    if function_name:
        print("API URL missing; invoking lambda directly")
        return _invoke_lambda(function_name, body)
    raise RuntimeError("Missing both API URL and Lambda function name")


def main() -> None:
    print("AgentCore Memory Demo")
    print("- Expect ok=true for memory_put/memory_get")
    print("- Expect ok=false with budget_exceeded for max_memory_ops=0")

    outputs = _load_outputs()
    api_url = outputs.get("AgentCoreMemoryApiUrl")
    function_name = outputs.get("AgentCoreMemoryFunctionName")

    if not api_url and not function_name:
        raise SystemExit("Missing AgentCore memory outputs. Run cdk deploy.")

    if api_url:
        print(f"Target API: {api_url.rstrip('/')}/agentcore/memory")
    elif function_name:
        print(f"Target Lambda fallback: {function_name}")
    print(f"TLS CA bundle: {_ca_bundle_path()}")

    os.environ.setdefault("ENABLE_AGENTCORE_MEMORY", "1")

    put_body = {
        "mode": "agentcore-memory",
        "budget": {"max_steps": 1, "max_tool_calls": 0, "max_model_calls": 0, "max_memory_ops": 1, "max_memory_bytes": 512},
        "requests": [{"op": "memory_put", "key": "demo", "value": {"value": "hello"}}],
    }
    get_body = {
        "mode": "agentcore-memory",
        "budget": {"max_steps": 1, "max_tool_calls": 0, "max_model_calls": 0, "max_memory_ops": 1, "max_memory_bytes": 512},
        "requests": [{"op": "memory_get", "key": "demo"}],
    }
    fail_body = {
        "mode": "agentcore-memory",
        "budget": {"max_steps": 1, "max_tool_calls": 0, "max_model_calls": 0, "max_memory_ops": 0, "max_memory_bytes": 0},
        "requests": [{"op": "memory_get", "key": "demo"}],
    }

    put_payload = _run(api_url, function_name, put_body)
    get_payload = _run(api_url, function_name, get_body)
    fail_payload = _run(api_url, function_name, fail_body)

    print("\n== memory_put (expect ok=true) ==")
    print(json.dumps(_sanitize(put_payload), indent=2))
    print("\n== memory_get (expect ok=true) ==")
    print(json.dumps(_sanitize(get_payload), indent=2))
    print("\n== budget_exceeded (expect ok=false) ==")
    print(json.dumps(_sanitize(fail_payload), indent=2))

    if not put_payload.get("ok"):
        raise SystemExit("memory_put did not return ok=true")
    if not get_payload.get("ok"):
        raise SystemExit("memory_get did not return ok=true")
    get_ops = get_payload.get("memory", {}).get("ops", [])
    got_value = get_ops[0].get("value") if get_ops else None
    if got_value != {"value": "hello"}:
        raise SystemExit("memory_get expected persisted value from previous memory_put")
    if put_payload.get("memory_enabled") is not True or get_payload.get("memory_enabled") is not True:
        raise SystemExit("memory_enabled expected true for normal requests")
    if fail_payload.get("ok") is not False:
        raise SystemExit("budget_exceeded expected ok=false")
    if fail_payload.get("error", {}).get("code") != "budget_exceeded":
        raise SystemExit("budget_exceeded expected error.code=budget_exceeded")


if __name__ == "__main__":
    main()