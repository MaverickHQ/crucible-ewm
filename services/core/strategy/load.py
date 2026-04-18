from __future__ import annotations

import json
from pathlib import Path

from services.core.strategy.types import StrategySpec


def load_strategy(path: str) -> StrategySpec:
    strategy_path = Path(path)
    payload = json.loads(strategy_path.read_text())
    return StrategySpec.model_validate(payload)
