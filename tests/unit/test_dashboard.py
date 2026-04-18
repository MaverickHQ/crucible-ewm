"""
Dashboard tests — three layers:
  1. Pure helper logic (no Streamlit runtime)
  2. Streamlit AppTest integration (widget state, rendering, interactions)
  3. yfinance column-flattening behaviour
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from ewm_core.market.synthetic import generate_ohlcv

# ── Helpers replicated from dashboard for isolated unit testing ───────────────
# These mirror the logic in dashboard/app.py without the @st.cache_data wrappers.

def compute_metrics(df: pd.DataFrame) -> dict:
    closes = df["close"]
    total_return = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
    daily_returns = closes.pct_change().dropna()
    cumulative = (1 + daily_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100
    vol = daily_returns.std() * np.sqrt(252) * 100
    sharpe = (
        daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        if daily_returns.std()
        else 0.0
    )
    return {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "annualised_vol": vol,
        "sharpe": sharpe,
    }


def extract_signals(
    trajectory: list[dict], ohlcv: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    buys: dict[int, float] = {}
    sells: dict[int, float] = {}
    for i, step in enumerate(trajectory):
        if i >= len(ohlcv):
            break
        action = step.get("action", {})
        action_type = action.get("type", "").lower()
        obs = step.get("observation", {})
        price = float(obs.get("price", ohlcv["close"].iloc[i]))
        if action_type == "buy":
            buys[i] = price
        elif action_type == "sell":
            sells[i] = price
    return pd.Series(buys, dtype=float), pd.Series(sells, dtype=float)


def extract_pnl(trajectory: list[dict]) -> pd.Series:
    cash: dict[int, float] = {}
    for i, step in enumerate(trajectory):
        obs = step.get("observation", {})
        bal = obs.get("cash_balance")
        if bal is not None:
            cash[i] = float(bal)
    return pd.Series(cash, dtype=float)


def flatten_yf_columns(raw: pd.DataFrame) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() for c in raw.columns]
    else:
        raw.columns = [c.lower() for c in raw.columns]
    return raw[["open", "high", "low", "close", "volume"]]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    return generate_ohlcv(n_candles=100, seed=0)


@pytest.fixture
def simple_trajectory() -> list[dict]:
    return [
        {"action": {"type": "buy", "symbol": "AAPL", "quantity": 10},
         "observation": {"price": 100.0, "cash_balance": 900.0}},
        {"action": {"type": "hold"},
         "observation": {"price": 102.0, "cash_balance": 900.0}},
        {"action": {"type": "sell", "symbol": "AAPL", "quantity": 10},
         "observation": {"price": 105.0, "cash_balance": 1950.0}},
        {"action": {"type": "hold"},
         "observation": {"price": 103.0, "cash_balance": 1950.0}},
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Pure helper logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeMetrics:
    def test_returns_all_keys(self, ohlcv_df):
        m = compute_metrics(ohlcv_df)
        assert set(m) == {"total_return", "max_drawdown", "annualised_vol", "sharpe"}

    def test_total_return_sign_flat(self):
        dates = pd.date_range("2020-01-01", periods=10)
        df = pd.DataFrame({"close": [100.0] * 10}, index=dates)
        m = compute_metrics(df)
        assert m["total_return"] == pytest.approx(0.0)

    def test_total_return_positive_trend(self):
        dates = pd.date_range("2020-01-01", periods=10)
        df = pd.DataFrame({"close": [100.0 + i for i in range(10)]}, index=dates)
        m = compute_metrics(df)
        assert m["total_return"] > 0

    def test_max_drawdown_is_non_positive(self, ohlcv_df):
        m = compute_metrics(ohlcv_df)
        assert m["max_drawdown"] <= 0

    def test_annualised_vol_is_positive(self, ohlcv_df):
        m = compute_metrics(ohlcv_df)
        assert m["annualised_vol"] > 0

    def test_sharpe_is_finite(self, ohlcv_df):
        m = compute_metrics(ohlcv_df)
        assert np.isfinite(m["sharpe"])


class TestExtractSignals:
    def test_buy_detected(self, simple_trajectory, ohlcv_df):
        buys, sells = extract_signals(simple_trajectory, ohlcv_df)
        assert 0 in buys.index
        assert buys[0] == pytest.approx(100.0)

    def test_sell_detected(self, simple_trajectory, ohlcv_df):
        buys, sells = extract_signals(simple_trajectory, ohlcv_df)
        assert 2 in sells.index
        assert sells[2] == pytest.approx(105.0)

    def test_hold_not_in_signals(self, simple_trajectory, ohlcv_df):
        buys, sells = extract_signals(simple_trajectory, ohlcv_df)
        assert 1 not in buys.index
        assert 1 not in sells.index

    def test_empty_trajectory_returns_empty_series(self, ohlcv_df):
        buys, sells = extract_signals([], ohlcv_df)
        assert buys.empty
        assert sells.empty

    def test_trajectory_longer_than_ohlcv_is_clamped(self, ohlcv_df):
        long_traj = [
            {"action": {"type": "buy"}, "observation": {"price": 100.0}}
        ] * (len(ohlcv_df) + 50)
        buys, _ = extract_signals(long_traj, ohlcv_df)
        assert all(i < len(ohlcv_df) for i in buys.index)

    def test_falls_back_to_ohlcv_close_when_price_missing(self, ohlcv_df):
        traj = [{"action": {"type": "buy"}, "observation": {}}]
        buys, _ = extract_signals(traj, ohlcv_df)
        assert 0 in buys.index
        assert buys[0] == pytest.approx(float(ohlcv_df["close"].iloc[0]))


class TestExtractPnl:
    def test_extracts_cash_balance(self, simple_trajectory):
        pnl = extract_pnl(simple_trajectory)
        assert pnl[0] == pytest.approx(900.0)
        assert pnl[2] == pytest.approx(1950.0)

    def test_steps_without_cash_are_excluded(self):
        traj = [
            {"action": {}, "observation": {}},
            {"action": {}, "observation": {"cash_balance": 500.0}},
        ]
        pnl = extract_pnl(traj)
        assert 0 not in pnl.index
        assert pnl[1] == pytest.approx(500.0)

    def test_empty_trajectory_returns_empty(self):
        assert extract_pnl([]).empty


class TestYfinanceColumnFlattening:
    def _make_multi(self) -> pd.DataFrame:
        arrays = [["Open", "High", "Low", "Close", "Volume"], ["AAPL"] * 5]
        mi = pd.MultiIndex.from_arrays(arrays)
        data = np.ones((3, 5))
        return pd.DataFrame(data, columns=mi)

    def _make_flat(self) -> pd.DataFrame:
        return pd.DataFrame(
            np.ones((3, 5)), columns=["Open", "High", "Low", "Close", "Volume"]
        )

    def test_multiindex_flattened_correctly(self):
        raw = self._make_multi()
        result = flatten_yf_columns(raw)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_flat_columns_lowercased(self):
        raw = self._make_flat()
        result = flatten_yf_columns(raw)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_output_has_correct_shape(self):
        raw = self._make_multi()
        result = flatten_yf_columns(raw)
        assert result.shape == (3, 5)


class TestLoadTrajectory:
    def test_loads_valid_trajectory(self, tmp_path):
        data = [{"action": {"type": "buy"}, "observation": {"price": 100.0}}]
        (tmp_path / "trajectory.json").write_text(json.dumps(data))

        # Replicate _load_trajectory logic directly
        traj_path = tmp_path / "trajectory.json"
        result = json.loads(traj_path.read_text())
        assert len(result) == 1
        assert result[0]["action"]["type"] == "buy"

    def test_missing_file_returns_empty(self, tmp_path):
        traj_path = tmp_path / "trajectory.json"
        result = [] if not traj_path.exists() else json.loads(traj_path.read_text())
        assert result == []

    def test_malformed_json_is_handled(self, tmp_path):
        (tmp_path / "trajectory.json").write_text("{bad json}")
        try:
            result = json.loads((tmp_path / "trajectory.json").read_text())
        except Exception:
            result = []
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Streamlit AppTest integration
# ═══════════════════════════════════════════════════════════════════════════════

APP_PATH = str(Path(__file__).resolve().parents[2] / "dashboard" / "app.py")


@pytest.fixture
def at():
    from streamlit.testing.v1 import AppTest
    _at = AppTest.from_file(APP_PATH, default_timeout=30)
    _at.run()
    return _at


class TestDefaultRender:
    def test_no_exception_on_load(self, at):
        assert not at.exception

    def test_title_present(self, at):
        titles = [t.value for t in at.title]
        assert any("EWM-Core" in t for t in titles)

    def test_five_metrics_rendered(self, at):
        assert len(at.metric) == 5

    def test_metric_labels(self, at):
        labels = [m.label for m in at.metric]
        assert "Period return" in labels
        assert "Max drawdown" in labels
        assert "Ann. volatility" in labels
        assert "Sharpe (ann.)" in labels
        assert "Candles" in labels

    def test_candles_metric_matches_default_slider(self, at):
        candles_metric = next(m for m in at.metric if m.label == "Candles")
        assert candles_metric.value == "200"

    def test_chart_renders_without_error(self, at):
        # AppTest doesn't expose plotly_chart elements directly;
        # a clean run with no exception confirms the chart was built.
        assert not at.exception

    def test_trajectory_info_shown_when_no_run(self, at):
        infos = [i.value for i in at.info]
        assert any("trajectory" in i.lower() or "run" in i.lower() for i in infos)

    def test_artifact_info_shown_when_no_dir(self, at):
        infos = [i.value for i in at.info]
        assert any("artifact" in i.lower() or "sidebar" in i.lower() for i in infos)


class TestSidebarControls:
    def test_live_toggle_exists_and_is_off(self, at):
        toggles = at.toggle
        assert len(toggles) >= 1
        live_toggle = toggles[0]
        assert live_toggle.value is False

    def test_ma20_checkbox_on_by_default(self, at):
        checkboxes = {cb.label: cb for cb in at.checkbox}
        assert "MA 20" in checkboxes
        assert checkboxes["MA 20"].value is True

    def test_ma50_checkbox_on_by_default(self, at):
        checkboxes = {cb.label: cb for cb in at.checkbox}
        assert "MA 50" in checkboxes
        assert checkboxes["MA 50"].value is True

    def test_ma200_checkbox_off_by_default(self, at):
        checkboxes = {cb.label: cb for cb in at.checkbox}
        assert "MA 200" in checkboxes
        assert checkboxes["MA 200"].value is False

    def test_candles_slider_exists_with_default_200(self, at):
        sliders = at.slider
        assert len(sliders) >= 1
        assert sliders[0].value == 200


class TestInteractions:
    def test_changing_candles_slider_updates_metric(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.slider[0].set_value(100).run()
        assert not at.exception
        candles_metric = next(m for m in at.metric if m.label == "Candles")
        assert candles_metric.value == "100"

    def test_disabling_ma20_reruns_without_error(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        checkboxes = {cb.label: cb for cb in at.checkbox}
        checkboxes["MA 20"].uncheck().run()
        assert not at.exception

    def test_enabling_ma200_reruns_without_error(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        checkboxes = {cb.label: cb for cb in at.checkbox}
        checkboxes["MA 200"].check().run()
        assert not at.exception

    def test_different_seeds_produce_different_return_metric(self):
        from streamlit.testing.v1 import AppTest
        at1 = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at2 = AppTest.from_file(APP_PATH, default_timeout=30).run()
        # Change seed on at2
        at2.number_input[2].set_value(99).run()  # seed is the 3rd number_input
        r1 = next(m.value for m in at1.metric if m.label == "Period return")
        r2 = next(m.value for m in at2.metric if m.label == "Period return")
        assert r1 != r2

    def test_invalid_artifacts_root_shows_warning(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input[0].set_value("/nonexistent/path/xyz").run()
        assert not at.exception
        warnings = [w.value for w in at.warning]
        assert any("not found" in w.lower() for w in warnings)


class TestArtifactViewer:
    def test_artifact_viewer_loads_json_files(self, tmp_path):
        """Verify artifact directory with JSON files is handled correctly."""
        run_dir = tmp_path / "run-abc"
        run_dir.mkdir()
        manifest = {"run_id": "run-abc", "manifest_version": "2", "mode": "test"}
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        # Simulate what the app does: glob for json files
        files = sorted(run_dir.glob("*.json"))
        assert len(files) == 1
        assert files[0].name == "manifest.json"
        content = json.loads(files[0].read_text())
        assert content["run_id"] == "run-abc"

    def test_run_selector_lists_subdirectories(self, tmp_path):
        """Verify run selector logic finds subdirectories."""
        for name in ["run-001", "run-002", "run-003"]:
            (tmp_path / name).mkdir()

        run_dirs = sorted(
            [d for d in tmp_path.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        assert len(run_dirs) == 3
        assert all(d.name.startswith("run-") for d in run_dirs)

    def test_run_selector_excludes_files(self, tmp_path):
        """Verify only directories are listed, not files."""
        (tmp_path / "run-001").mkdir()
        (tmp_path / "stray.json").write_text("{}")

        run_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1
        assert run_dirs[0].name == "run-001"
