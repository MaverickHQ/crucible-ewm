from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    description: str


class StrategyUniverse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: List[str]

    @field_validator("symbols")
    @classmethod
    def _ensure_symbols(cls, value: List[str]) -> List[str]:
        symbols = [symbol.strip().upper() for symbol in value if symbol.strip()]
        if not symbols:
            raise ValueError("Strategy universe must include at least one symbol.")
        return symbols


class StrategyTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_frequency_steps: int = Field(1, ge=1)


class StrategySizing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_position_qty_per_symbol: Union[int, float] = Field(..., gt=0)
    order_qty: Union[int, float] = Field(..., gt=0)
    max_new_exposure_per_step: Optional[float] = Field(default=None, gt=0)


class ThresholdPriceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field("threshold_price", pattern="^threshold_price$")
    symbol: str
    buy_below: Optional[float] = Field(default=None, gt=0)
    sell_above: Optional[float] = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Rule symbol must be non-empty.")
        return symbol


class SmaCrossoverRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field("sma_crossover", pattern="^sma_crossover$")
    symbol: str
    short_window: int = Field(..., ge=1)
    long_window: int = Field(..., ge=2)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Rule symbol must be non-empty.")
        return symbol


class MeanReversionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field("mean_reversion_zscore", pattern="^mean_reversion_zscore$")
    symbol: str
    window: int = Field(..., ge=2)
    z_buy_below: float = Field(..., lt=0)
    z_sell_above: float = Field(..., gt=0)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Rule symbol must be non-empty.")
        return symbol


RuleSpec = Union[ThresholdPriceRule, SmaCrossoverRule, MeanReversionRule]


class StrategySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: StrategyMetadata
    universe: StrategyUniverse
    timing: StrategyTiming = Field(default_factory=StrategyTiming)
    sizing: StrategySizing
    rules: List[RuleSpec] = Field(..., min_length=1)
