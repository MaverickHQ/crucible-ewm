from __future__ import annotations

import json
import os

from services.aws.adapters.ddb_stores import DdbRunStore


def handler(event, context):
    payload = event if isinstance(event, dict) else json.loads(event)

    run_id = payload["run_id"]
    runs_table = os.environ["RUNS_TABLE"]
    bucket_name = os.environ["ARTIFACT_BUCKET"]

    run_store = DdbRunStore(table_name=runs_table)
    run = run_store.get_run(run_id)

    if not run:
        return {"run_id": run_id, "found": False}

    return {
        "run_id": run_id,
        "found": True,
        "approved": run.approved,
        "rejected_step_index": run.rejected_step_index,
        "artifact_s3_prefix": f"s3://{bucket_name}/artifacts/{run_id}",
    }
