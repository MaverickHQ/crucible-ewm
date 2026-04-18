from __future__ import annotations

import json
import os

from services.aws.adapters.ddb_stores import DdbRunStore, DdbStateStore
from services.core.execution import execute_run


def handler(event, context):
    payload = event if isinstance(event, dict) else json.loads(event)

    run_id = payload["run_id"]
    state_table = os.environ["STATE_TABLE"]
    runs_table = os.environ["RUNS_TABLE"]

    state_store = DdbStateStore(table_name=state_table)
    run_store = DdbRunStore(table_name=runs_table)

    execution = execute_run(run_store, state_store, run_id)

    return {
        "run_id": run_id,
        "executed": execution.approved,
        "message": execution.message,
        "state_summary": execution.state.to_dict() if execution.state else None,
    }
