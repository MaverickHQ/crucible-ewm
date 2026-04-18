from ewm_core.agentcore_tools import (
    ToolName,
    ToolRegistry,
    ToolRequest,
    ToolResult,
)


def test_registry_invokes_tool():
    registry = ToolRegistry()

    def handler(request: ToolRequest) -> ToolResult:
        return ToolResult(ok=True, output={"name": request.name.value})

    registry.register(ToolName.GET_PRICE_CONTEXT, handler)
    result = registry.invoke(ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}))

    assert result.ok is True
    assert result.output["name"] == "get_price_context"


def test_registry_unknown_tool():
    registry = ToolRegistry()

    result = registry.invoke(ToolRequest(name=ToolName.GET_PRICE_CONTEXT, args={}))

    assert result.ok is False
    assert "unknown tool" in (result.error or "")
