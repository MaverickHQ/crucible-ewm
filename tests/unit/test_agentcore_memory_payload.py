from services.aws.handlers import agentcore_memory_handler


class _DummyS3:
    def put_object(self, **kwargs):
        return {"ok": True}


def test_agentcore_memory_payload_has_required_fields(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")
    monkeypatch.setenv("ENABLE_AGENTCORE_MEMORY", "0")
    monkeypatch.setattr(agentcore_memory_handler.boto3, "client", lambda *_: _DummyS3())

    response = agentcore_memory_handler.handler({"mode": "agentcore-memory"}, None)

    assert response["ok"] is True
    assert response["mode"] == "agentcore-memory"
    assert response["message"] == "memory disabled"
    assert response["budget"]["max_memory_ops"] == 1
    assert response["budget"]["max_memory_bytes"] == 512
    assert response["budget_state"]["memory_ops"] == 0
    assert response["budget_state"]["memory_bytes"] == 0


def test_agentcore_memory_payload_reports_enabled_when_configured(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")
    monkeypatch.setenv("ENABLE_AGENTCORE_MEMORY", "1")
    monkeypatch.setenv("AGENTCORE_MEMORY_BACKEND", "in-memory")
    monkeypatch.setattr(agentcore_memory_handler.boto3, "client", lambda *_: _DummyS3())

    payload = {
        "mode": "agentcore-memory",
        "budget": {
            "max_steps": 1,
            "max_tool_calls": 0,
            "max_model_calls": 0,
            "max_memory_ops": 1,
            "max_memory_bytes": 1024,
        },
        "requests": [{"op": "memory_put", "key": "alpha", "value": {"v": 1}}],
    }

    response = agentcore_memory_handler.handler(payload, None)

    assert response["ok"] is True
    assert response["memory_enabled"] is True
