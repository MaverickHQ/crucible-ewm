from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_outputs(path: Path) -> Dict[str, str]:
    payload = json.loads(path.read_text())
    if "Outputs" in payload:
        outputs = payload.get("Outputs", {})
        return {key: value["Value"] for key, value in outputs.items()}
    return payload.get("BeyondTokensStack", {})
