from services.aws.handlers import agentcore_memory_handler
from services.core.agentcore_memory import store as memory_store_module
from services.core.agentcore_memory.store import estimate_memory_bytes


class _DummyS3:
    def put_object(self, **kwargs):
        return {"ok": True}


class _DdbShouldNotBeCalled:
    def __init__(self):
        self.called = False

    def __call__(self, service_name):
        if service_name == "dynamodb":
            self.called = True
            raise AssertionError("dynamodb client must not be created when precheck fails")
        return _DummyS3()


def test_budget_enforced_for_memory_ops(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")
    monkeypatch.setenv("ENABLE_AGENTCORE_MEMORY", "1")
    monkeypatch.setattr(agentcore_memory_handler.boto3, "client", lambda *_: _DummyS3())

    payload = {
        "mode": "agentcore-memory",
        "budget": {
            "max_steps": 1,
            "max_tool_calls": 0,
            "max_model_calls": 0,
            "max_memory_ops": 0,
            "max_memory_bytes": 1,
        },
        "requests": [{"op": "memory_get", "key": "alpha"}],
    }

    response = agentcore_memory_handler.handler(payload, None)

    assert response["ok"] is False
    assert response["error"]["code"] == "budget_exceeded"
    assert response["error"]["limiter"] == "max_memory_ops"
    assert response["memory_enabled"] is True
    assert response["budget_state"]["memory_ops"] == 0
    assert response["budget_state"]["memory_bytes"] == 0
    assert response["memory"]["ops"] == []


def test_budget_precheck_happens_before_dynamodb_client_creation(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")
    monkeypatch.setenv("ENABLE_AGENTCORE_MEMORY", "1")
    monkeypatch.setenv("AGENTCORE_MEMORY_BACKEND", "dynamodb")
    monkeypatch.setenv("AGENTCORE_MEMORY_TABLE", "memory-table")

    ddb_guard = _DdbShouldNotBeCalled()
    monkeypatch.setattr(agentcore_memory_handler.boto3, "client", ddb_guard)
    monkeypatch.setattr(memory_store_module.boto3, "client", ddb_guard)

    payload = {
        "mode": "agentcore-memory",
        "budget": {
            "max_steps": 1,
            "max_tool_calls": 0,
            "max_model_calls": 0,
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        },
        "requests": [{"op": "memory_get", "key": "alpha"}],
    }

    response = agentcore_memory_handler.handler(payload, None)

    assert response["ok"] is False
    assert response["error"]["code"] == "budget_exceeded"
    assert ddb_guard.called is False


def test_budget_enforced_for_memory_bytes(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")
    monkeypatch.setenv("ENABLE_AGENTCORE_MEMORY", "1")

    payload = {"note": "hello"}
    payload_bytes = estimate_memory_bytes(payload)

    response = agentcore_memory_handler._record_memory_op(  # pylint: disable=protected-access
        agentcore_memory_handler.BudgetState(),
        payload,
        agentcore_memory_handler.Budget(
            max_steps=1,
            max_tool_calls=0,
            max_model_calls=0,
            max_memory_ops=1,
            max_memory_bytes=payload_bytes - 1,
        ),
    )

    assert response == "max_memory_bytes"
