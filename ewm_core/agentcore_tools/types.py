from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolName(str, Enum):
    GET_PRICE_CONTEXT = "get_price_context"
    EVALUATE_STRATEGY = "evaluate_strategy"
    SIMULATE_AND_VERIFY = "simulate_and_verify"


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ToolName
    args: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_memory_ops: int = Field(ge=0)
    max_memory_bytes: int = Field(ge=0)


class BudgetState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    memory_ops: int = 0
    memory_bytes: int = 0

    def increment_step(self) -> None:
        self.steps += 1

    def increment_tool_calls(self) -> None:
        self.tool_calls += 1

    def increment_model_calls(self) -> None:
        self.model_calls += 1

    def increment_memory_ops(self) -> None:
        self.memory_ops += 1

    def increment_memory_bytes(self, delta: int) -> None:
        self.memory_bytes += delta

    def within_budget(self, budget: Budget) -> bool:
        return (
            self.steps <= budget.max_steps
            and self.tool_calls <= budget.max_tool_calls
            and self.model_calls <= budget.max_model_calls
            and self.memory_ops <= budget.max_memory_ops
            and self.memory_bytes <= budget.max_memory_bytes
        )
