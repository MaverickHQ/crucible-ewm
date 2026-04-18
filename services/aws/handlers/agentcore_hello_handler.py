from __future__ import annotations

import json
import os
import uuid
from typing import Dict

import boto3


def _artifact_keys(run_id: str) -> Dict[str, str]:
    prefix = f"artifacts/{run_id}"
    return {
        "artifact_prefix": prefix,
        "decision_key": f"{prefix}/decision.json",
        "report_key": f"{prefix}/report.md",
    }


def _decision_payload(run_id: str) -> Dict[str, object]:
    return {
        "run_id": run_id,
        "mode": "agentcore-hello",
        "message": "hello from agentcore (no model calls)",
        "budgets": {
            "max_steps": 1,
            "max_tool_calls": 0,
            "max_model_calls": 0,
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        },
    }


def _report_body(run_id: str, bucket_name: str, artifact_prefix: str) -> str:
    return "\n".join(
        [
            "# AgentCore Hello Report",
            "",
            f"Run ID: {run_id}",
            f"Artifacts: s3://{bucket_name}/{artifact_prefix}/",
            "",
            "## Replay",
            "(placeholder)",
            "",
        ]
    )


def _response_payload(run_id: str, bucket_name: str, artifact_prefix: str) -> Dict[str, object]:
    return {
        "ok": True,
        "run_id": run_id,
        "mode": "agentcore-hello",
        "message": "hello from agentcore (no model calls)",
        "artifacts": {
            "artifact_dir": f"s3://{bucket_name}/{artifact_prefix}/",
        },
        "budgets": _decision_payload(run_id)["budgets"],
    }


def handler(event, context):
    bucket_name = os.environ["ARTIFACT_BUCKET"]
    run_id = str(uuid.uuid4())
    keys = _artifact_keys(run_id)
    decision_payload = _decision_payload(run_id)
    report_body = _report_body(run_id, bucket_name, keys["artifact_prefix"])

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["decision_key"],
        Body=json.dumps(decision_payload, indent=2).encode("utf-8"),
    )
    s3.put_object(
        Bucket=bucket_name,
        Key=keys["report_key"],
        Body=report_body.encode("utf-8"),
    )

    payload = _response_payload(run_id, bucket_name, keys["artifact_prefix"])

    if isinstance(event, dict) and event.get("requestContext", {}).get("http"):
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(payload),
        }

    return payload
