from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class MarketPath:
    symbols: List[str]
    steps: List[Dict[str, float]]

    def price_context(self, step_index: int) -> Dict[str, float]:
        if step_index < 0 or step_index >= len(self.steps):
            raise IndexError("Step index out of range")
        return dict(self.steps[step_index])

    @classmethod
    def from_fixture(cls, path: Path) -> "MarketPath":
        data = json.loads(path.read_text())
        return cls(symbols=data["symbols"], steps=data["steps"])
