from services.aws.handlers import agentcore_hello_handler


def test_agentcore_hello_payload_has_required_fields(monkeypatch):
    monkeypatch.setenv("ARTIFACT_BUCKET", "example-bucket")

    payload = agentcore_hello_handler._response_payload(
        "run-123",
        "example-bucket",
        "artifacts/run-123",
    )

    assert payload["ok"] is True
    assert payload["run_id"] == "run-123"
    assert payload["mode"] == "agentcore-hello"
    assert payload["message"] == "hello from agentcore (no model calls)"
    assert payload["artifacts"]["artifact_dir"].endswith("/artifacts/run-123/")

    budgets = payload["budgets"]
    assert budgets["max_steps"] == 1
    assert budgets["max_tool_calls"] == 0
    assert budgets["max_model_calls"] == 0
    assert budgets["max_memory_ops"] == 0
    assert budgets["max_memory_bytes"] == 0
