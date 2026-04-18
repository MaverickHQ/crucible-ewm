from __future__ import annotations

from typing import List, Tuple

from ewm_core.agentcore_tools.registry import ToolRegistry
from ewm_core.agentcore_tools.types import Budget, BudgetState, ToolRequest, ToolResult


def run_tool_loop(
    tool_requests: List[ToolRequest],
    registry: ToolRegistry,
    budget: Budget,
) -> Tuple[List[ToolResult], BudgetState]:
    results: List[ToolResult] = []
    budget_state = BudgetState()

    for request in tool_requests:
        budget_state.increment_step()
        if budget_state.steps > budget.max_steps:
            results.append(ToolResult(ok=False, error="budget exceeded: max_steps"))
            break

        budget_state.increment_tool_calls()
        if budget_state.tool_calls > budget.max_tool_calls:
            results.append(ToolResult(ok=False, error="budget exceeded: max_tool_calls"))
            break

        if budget_state.model_calls > budget.max_model_calls:
            results.append(ToolResult(ok=False, error="budget exceeded: max_model_calls"))
            break

        if budget_state.memory_ops > budget.max_memory_ops:
            results.append(ToolResult(ok=False, error="budget exceeded: max_memory_ops"))
            break

        if budget_state.memory_bytes > budget.max_memory_bytes:
            results.append(ToolResult(ok=False, error="budget exceeded: max_memory_bytes"))
            break

        result = registry.invoke(request)
        results.append(result)
        if not result.ok:
            break

    return results, budget_state
