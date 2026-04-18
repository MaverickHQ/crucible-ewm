from __future__ import annotations

import json
from pathlib import Path

import boto3
from botocore.stub import ANY, Stubber

from services.aws.handlers import agentcore_loop_handler
from ewm_core.persistence.agentcore_loop_persistence import upload_dir_to_s3
from ewm_core.persistence.runs_dynamo import put_run


def test_upload_dir_to_s3_uploads_recursive(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    (root / "nested").mkdir(parents=True)
    (root / "a.json").write_text("{}")
    (root / "nested" / "b.json").write_text("{}")

    s3 = boto3.client("s3", region_name="us-east-1")
    stub = Stubber(s3)
    stub.add_response(
        "put_object",
        {},
        {"Bucket": "bucket", "Key": "agentcore/loop/run-1/a.json", "Body": ANY},
    )
    stub.add_response(
        "put_object",
        {},
        {"Bucket": "bucket", "Key": "agentcore/loop/run-1/nested/b.json", "Body": ANY},
    )
    stub.activate()

    monkeypatch.setattr(
        "ewm_core.persistence.agentcore_loop_persistence.boto3.client",
        lambda *_: s3,
    )

    out = upload_dir_to_s3(root, "bucket", "agentcore/loop/run-1")
    assert out == "s3://bucket/agentcore/loop/run-1"
    stub.assert_no_pending_responses()
    stub.deactivate()


def test_put_run_writes_expected_item_to_ddb() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    stub = Stubber(ddb)
    stub.add_response(
        "put_item",
        {},
        {
            "TableName": "runs-table",
            "Item": {
                "run_id": {"S": "run-1"},
                "created_at": {"S": ANY},
                "mode": {"S": "agentcore-loop"},
                "symbols": {"L": [{"S": "AAPL"}, {"S": "MSFT"}]},
                "steps": {"N": "5"},
                "ok": {"BOOL": True},
                "http_status": {"N": "200"},
                "duration_ms": {"N": "123"},
                "final_state": {
                    "M": {
                        "cash_balance": {"N": "500.0"},
                        "positions": {"M": {"AAPL": {"N": "2.0"}}},
                    }
                },
                "artifact_dir": {"S": "/tmp/agentcore-loop-1"},
                "error": {"NULL": True},
                "trace_id": {"S": "trace-1"},
                "request_id": {"S": "req-1"},
            },
        },
    )
    stub.activate()

    put_run(
        "runs-table",
        {
            "run_id": "run-1",
            "created_at": "2026-02-16T10:00:00+00:00",
            "mode": "agentcore-loop",
            "symbols": ["AAPL", "MSFT"],
            "steps": 5,
            "ok": True,
            "http_status": 200,
            "duration_ms": 123,
            "final_state": {"cash_balance": 500.0, "positions": {"AAPL": 2.0}},
            "artifact_dir": "/tmp/agentcore-loop-1",
            "error": None,
            "trace_id": "trace-1",
            "request_id": "req-1",
        },
        client=ddb,
    )

    stub.assert_no_pending_responses()
    stub.deactivate()


def test_handler_persistence_failure_is_best_effort(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RUNS_TABLE", "runs-table")

    monkeypatch.setattr(
        agentcore_loop_handler,
        "run_agentcore_loop",
        lambda _req: {
            "ok": True,
            "run_id": "run-2",
            "mode": "agentcore-loop",
            "steps": 1,
            "tape_length": 1,
            "execution_count": 1,
            "final_state": {"cash_balance": 1000.0, "positions": {}},
            "artifact_dir": "/tmp/agentcore-loop-2",
        },
    )
    monkeypatch.setattr(
        agentcore_loop_handler,
        "put_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ddb down")),
    )

    payload = {"body": json.dumps({"mode": "agentcore-loop"})}
    response = agentcore_loop_handler.handler(payload, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["ok"] is True

    captured = capsys.readouterr()
    assert "run_persistence_failed" in captured.out


def test_handler_persists_error_payload_for_invalid_budget(monkeypatch) -> None:
    monkeypatch.setenv("RUNS_TABLE", "runs-table")

    calls: list[tuple[str, dict]] = []

    def _record(table_name: str, run_record: dict, **_kwargs) -> None:
        calls.append((table_name, run_record))

    monkeypatch.setattr(agentcore_loop_handler, "put_run", _record)

    payload = {
        "mode": "agentcore-loop",
        "budgets": {
            "max_steps": 2,
            "max_tool_calls": 10,
            "max_model_calls": 1,
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        },
    }

    response = agentcore_loop_handler.handler({"body": json.dumps(payload)}, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_budget"

    assert len(calls) == 1
    table_name, run_record = calls[0]
    assert table_name == "runs-table"
    assert run_record["ok"] is False
    assert run_record["http_status"] == 400
    assert run_record["error"]["code"] == "invalid_budget"
    assert run_record["run_id"] == body["run_id"]
