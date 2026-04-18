from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from services.core.loop.types import ExecutionBundle, ExecutionRow


def write_execution_ledger(path: Path, rows: List[ExecutionRow]) -> None:
    path.write_text(json.dumps([row.to_dict() for row in rows], indent=2))


def write_execution_bundle(path: Path, bundles: List[ExecutionBundle]) -> None:
    payload: Dict[str, object] = {"executions": [bundle.to_dict() for bundle in bundles]}
    path.write_text(json.dumps(payload, indent=2))
