from __future__ import annotations

import numpy as np
import pandas as pd


def generate_ohlcv(
    n_candles: int = 100,
    drift: float = 0.0003,
    volatility: float = 0.012,
    seed: int = 42,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Generate synthetic OHLCV candles via GBM. Deterministic given same seed."""
    if n_candles <= 0:
        raise ValueError("n_candles must be positive")
    if start_price <= 0:
        raise ValueError("start_price must be positive")

    rng = np.random.default_rng(seed)

    # GBM log-returns for close prices
    returns = rng.normal(drift, volatility, n_candles)
    log_prices = np.log(start_price) + np.cumsum(returns)
    closes = np.exp(log_prices)

    # Simulate intra-candle high/low/open from close
    opens = np.empty(n_candles)
    opens[0] = start_price
    opens[1:] = closes[:-1]

    noise = np.abs(rng.normal(0, volatility, n_candles))
    highs = np.maximum(opens, closes) * (1 + noise)
    lows = np.minimum(opens, closes) * (1 - noise)

    volumes = rng.integers(100_000, 10_000_000, n_candles).astype(float)

    dates = pd.date_range("2020-01-01", periods=n_candles, freq="D")

    return pd.DataFrame(
        {
            "open": np.round(opens, 4),
            "high": np.round(highs, 4),
            "low": np.round(lows, 4),
            "close": np.round(closes, 4),
            "volume": volumes,
        },
        index=dates,
    )
