from __future__ import annotations

import json
from typing import Any

import boto3


def _to_ddb_attr(value: Any) -> dict[str, Any]:
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float)):
        return {"N": str(value)}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, dict):
        return {"M": {str(k): _to_ddb_attr(v) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        return {"L": [_to_ddb_attr(v) for v in value]}
    return {"S": json.dumps(value, default=str)}


def put_run(table_name: str, run_record: dict[str, Any], client: Any | None = None) -> None:
    if not table_name:
        raise ValueError("table_name is required")
    if not run_record.get("run_id"):
        raise ValueError("run_record.run_id is required")

    ddb = client or boto3.client("dynamodb")
    item = {key: _to_ddb_attr(value) for key, value in run_record.items()}
    ddb.put_item(TableName=table_name, Item=item)
