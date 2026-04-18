
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.aws.utils.output_loader import load_outputs

OUTPUTS_PATH = Path(
    os.environ.get("AWS_OUTPUTS_PATH", ROOT / "infra" / "cdk" / "cdk-outputs.json")
)


def _sanitize(payload: dict) -> dict:
    if "artifacts" in payload and "artifact_dir" in payload["artifacts"]:
        payload = dict(payload)
        payload["artifacts"] = dict(payload["artifacts"])
        payload["artifacts"]["artifact_dir"] = "s3://<redacted>/artifacts/<run_id>/"
    return payload


def _invoke_api(api_url: str) -> dict:
    url = api_url.rstrip("/") + "/agentcore/base"
    request = urllib.request.Request(
        url,
        data=json.dumps({}).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    context = ssl.create_default_context()
    if os.environ.get("ALLOW_INSECURE_HTTPS") == "1":
        context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=10, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def _invoke_lambda(function_name: str) -> dict:
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps({}).encode("utf-8"),
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


def main() -> None:
    outputs = _load_outputs()
    api_url = outputs.get("AgentCoreHelloApiUrl")
    function_name = outputs.get("AgentCoreHelloFunctionName")

    if not api_url and not function_name:
        raise SystemExit("Missing AgentCore hello outputs. Run cdk deploy.")

    if api_url:
        try:
            payload = _invoke_api(api_url)
        except Exception:
            payload = _invoke_lambda(function_name)
    else:
        payload = _invoke_lambda(function_name)

    if not payload.get("ok"):
        raise SystemExit("AgentCore hello did not return ok=true")

    print(json.dumps(_sanitize(payload), indent=2))


if __name__ == "__main__":
    main()