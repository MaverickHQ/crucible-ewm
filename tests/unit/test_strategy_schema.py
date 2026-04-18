import json

import pytest

from services.core.strategy.load import load_strategy
from services.core.strategy.types import StrategySpec


def test_strategy_schema_valid(tmp_path) -> None:
    payload = {
        "metadata": {"name": "Demo", "version": "1.0", "description": "Test"},
        "universe": {"symbols": ["AAPL"]},
        "timing": {"evaluation_frequency_steps": 1},
        "sizing": {
            "max_position_qty_per_symbol": 2,
            "order_qty": 1,
            "max_new_exposure_per_step": 100,
        },
        "rules": [
            {
                "type": "threshold_price",
                "symbol": "AAPL",
                "buy_below": 100.0,
                "sell_above": 110.0,
            }
        ],
    }

    path = tmp_path / "strategy.json"
    path.write_text(json.dumps(payload))

    strategy = load_strategy(str(path))
    assert isinstance(strategy, StrategySpec)
    assert strategy.universe.symbols == ["AAPL"]


def test_strategy_schema_rejects_unknown_fields(tmp_path) -> None:
    payload = {
        "metadata": {"name": "Demo", "version": "1.0", "description": "Test"},
        "universe": {"symbols": ["AAPL"]},
        "sizing": {"max_position_qty_per_symbol": 2, "order_qty": 1},
        "rules": [
            {
                "type": "threshold_price",
                "symbol": "AAPL",
                "buy_below": 100.0,
                "sell_above": 110.0,
                "extra": "nope",
            }
        ],
    }

    path = tmp_path / "strategy.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(Exception):
        load_strategy(str(path))


def test_strategy_schema_rejects_bad_enum(tmp_path) -> None:
    payload = {
        "metadata": {"name": "Demo", "version": "1.0", "description": "Test"},
        "universe": {"symbols": ["AAPL"]},
        "sizing": {"max_position_qty_per_symbol": 2, "order_qty": 1},
        "rules": [
            {
                "type": "threshold_price",
                "symbol": "AAPL",
                "buy_below": -1.0,
                "sell_above": 110.0,
            }
        ],
    }

    path = tmp_path / "strategy.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(Exception):
        load_strategy(str(path))
