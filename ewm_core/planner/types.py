from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PlanStep:
    """
    A minimal plan step for Pack 19 Block 1.

    We keep this intentionally simple and local-only:
    - tool: name of the tool/operation (string)
    - args: dict payload
    - rationale: short explanation for observability/debugging
    """

    tool: str
    args: Dict[str, Any]
    rationale: str


@dataclass(frozen=True)
class Plan:
    """
    A Plan is a list of PlanStep objects plus optional metadata.
    """

    steps: List[PlanStep]
    meta: Dict[str, Any]


@dataclass(frozen=True)
class PlannerError:
    code: str
    message: str


@dataclass(frozen=True)
class PlannerRejection:
    rejected_step_index: int
    violations: List[Dict[str, str]]


@dataclass
class PlannerResult:
    plan: List[Any]
    planner_name: str
    metadata: Dict[str, Any]
    error: Optional[PlannerError] = None
    rejection: Optional[PlannerRejection] = None
