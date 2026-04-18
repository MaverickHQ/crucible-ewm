from __future__ import annotations

import pandas as pd
import pytest

from ewm_core.market.synthetic import generate_ohlcv


def test_returns_dataframe_with_correct_shape():
    df = generate_ohlcv(n_candles=50)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (50, 5)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_deterministic_given_same_seed():
    a = generate_ohlcv(seed=1)
    b = generate_ohlcv(seed=1)
    pd.testing.assert_frame_equal(a, b)


def test_different_seeds_produce_different_output():
    a = generate_ohlcv(seed=1)
    b = generate_ohlcv(seed=2)
    assert not a.equals(b)


def test_ohlcv_invariants():
    df = generate_ohlcv(n_candles=200, seed=99)
    assert (df["high"] >= df["open"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["open"]).all()
    assert (df["low"] <= df["close"]).all()
    assert (df["volume"] > 0).all()
    assert (df["close"] > 0).all()


def test_start_price_is_respected():
    df = generate_ohlcv(n_candles=10, start_price=500.0, seed=0)
    assert abs(df["open"].iloc[0] - 500.0) < 0.01


def test_invalid_n_candles_raises():
    with pytest.raises(ValueError):
        generate_ohlcv(n_candles=0)


def test_invalid_start_price_raises():
    with pytest.raises(ValueError):
        generate_ohlcv(start_price=-1.0)
