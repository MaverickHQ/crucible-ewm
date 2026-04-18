from __future__ import annotations

import math
import random
from typing import Dict, List

from services.core.market.path import MarketPath

DEFAULT_BASELINES: Dict[str, float] = {
    "AAPL": 100.0,
    "MSFT": 198.0,
    "AMZN": 170.0,
    "NVDA": 850.0,
    "TSLA": 200.0,
    "GOOGL": 150.0,
    "META": 450.0,
    "SPY": 500.0,
    "QQQ": 420.0,
}


def _normalize_tickers(tickers: List[str]) -> List[str]:
    normalized = []
    for ticker in tickers:
        if not ticker:
            continue
        normalized.append(ticker.strip().upper())
    if not normalized:
        raise ValueError("At least one ticker is required.")
    return normalized


def _baseline_for(ticker: str, baselines: Dict[str, float]) -> float:
    baseline = baselines.get(ticker)
    if baseline is None:
        raise ValueError(f"Missing baseline for ticker: {ticker}")
    return float(baseline)


def _clamp_price(price: float) -> float:
    return max(price, 0.01)


def generate_market_path(
    tickers: List[str],
    n_steps: int,
    seed: int = 42,
    baselines: Dict[str, float] | None = None,
) -> MarketPath:
    if n_steps <= 0:
        raise ValueError("n_steps must be positive.")

    rng = random.Random(seed)
    normalized = _normalize_tickers(tickers)
    baseline_map = baselines or DEFAULT_BASELINES

    prices = {ticker: _baseline_for(ticker, baseline_map) for ticker in normalized}
    steps = []

    drift = 0.0003
    volatility = 0.012
    jump_chance = 0.05
    jump_low = -0.05
    jump_high = 0.05

    for _ in range(n_steps):
        step_payload = {}
        for ticker in normalized:
            prev = prices[ticker]
            shock = rng.gauss(0.0, volatility)
            growth = drift + shock
            if rng.random() < jump_chance:
                growth += rng.uniform(jump_low, jump_high)

            next_price = prev * math.exp(growth)
            next_price = round(_clamp_price(next_price), 2)
            prices[ticker] = next_price
            step_payload[ticker] = next_price
        steps.append(step_payload)

    return MarketPath(symbols=normalized, steps=steps)
