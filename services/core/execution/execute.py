from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.core.persistence import RunStore, StateStore
from services.core.state import State


@dataclass
class ExecutionResult:
    run_id: str
    approved: bool
    state: Optional[State]
    message: str


def execute_run(run_store: RunStore, state_store: StateStore, run_id: str) -> ExecutionResult:
    run = run_store.get_run(run_id)
    if not run:
        return ExecutionResult(run_id=run_id, approved=False, state=None, message="Run not found.")

    if not run.approved:
        return ExecutionResult(
            run_id=run_id,
            approved=False,
            state=None,
            message="Run is rejected.",
        )

    current_state = state_store.get_current_state()
    final_state = run.trajectory[-1]

    if current_state and current_state.to_dict() == final_state.to_dict():
        return ExecutionResult(
            run_id=run_id,
            approved=True,
            state=current_state,
            message="Run already executed.",
        )

    state_store.update_state(final_state)
    return ExecutionResult(
        run_id=run_id,
        approved=True,
        state=final_state,
        message="Run executed successfully.",
    )
