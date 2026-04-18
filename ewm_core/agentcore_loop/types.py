from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DEFAULT_STRATEGY_PATH = "examples/strategies/threshold_demo.json"


@dataclass(frozen=True)
class LoopBudgets:
    max_steps: int = 5
    max_tool_calls: int = 10
    max_model_calls: int = 0
    max_memory_ops: int = 0
    max_memory_bytes: int = 0


@dataclass(frozen=True)
class LoopRequest:
    budgets: LoopBudgets
    seed: int = 7
    symbols: tuple[str, ...] = ("AAPL", "MSFT")
    starting_cash: float = 1000.0
    steps: int = 5
    write_artifacts: bool = True
    upload_s3: bool = True  # Upload artifacts to S3 when True
    mode: str = "agentcore-loop"
    strategy_path: str = field(default=DEFAULT_STRATEGY_PATH)
    run_id: Optional[str] = None  # Optional run_id for consistency across artifacts
