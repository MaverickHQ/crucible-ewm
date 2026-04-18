from services.core.agentcore_tools import (
    Budget,
    ToolName,
    ToolRegistry,
    ToolRequest,
    ToolResult,
    run_tool_loop,
)


def test_budget_exceeded_by_tool_calls():
    registry = ToolRegistry()

    def noop_tool(request: ToolRequest) -> ToolResult:
        return ToolResult(ok=True, output={"ok": True})

    registry.register(ToolName.GET_PRICE_CONTEXT, noop_tool)
    requests = [
        ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}),
        ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}),
    ]
    budget = Budget(
        max_steps=5,
        max_tool_calls=1,
        max_model_calls=0,
        max_memory_ops=0,
        max_memory_bytes=0,
    )

    results, state = run_tool_loop(requests, registry, budget)

    assert state.tool_calls == 2
    assert results[-1].ok is False
    assert "max_tool_calls" in (results[-1].error or "")


def test_budget_exceeded_by_steps():
    registry = ToolRegistry()

    def noop_tool(request: ToolRequest) -> ToolResult:
        return ToolResult(ok=True, output={"ok": True})

    registry.register(ToolName.GET_PRICE_CONTEXT, noop_tool)
    requests = [
        ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}),
        ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}),
    ]
    budget = Budget(
        max_steps=1,
        max_tool_calls=5,
        max_model_calls=0,
        max_memory_ops=0,
        max_memory_bytes=0,
    )

    results, state = run_tool_loop(requests, registry, budget)

    assert state.steps == 2
    assert results[-1].ok is False
    assert "max_steps" in (results[-1].error or "")
