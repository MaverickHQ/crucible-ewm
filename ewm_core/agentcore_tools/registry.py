from __future__ import annotations

from typing import Callable, Dict

from ewm_core.agentcore_tools.types import ToolName, ToolRequest, ToolResult

ToolFn = Callable[[ToolRequest], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[ToolName, ToolFn] = {}

    def register(self, name: ToolName, fn: ToolFn) -> None:
        self._tools[name] = fn

    def invoke(self, request: ToolRequest) -> ToolResult:
        tool = self._tools.get(request.name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {request.name}")
        return tool(request)
