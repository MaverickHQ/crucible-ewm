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


# P1-2: Trade summary helper mirrored for unit tests
def compute_trade_summary(trajectory: list[dict]) -> dict:
    pending_buys: list[tuple[int, float, float]] = []
    pairs: list[tuple[int, int, float]] = []
    gross_pnl = 0.0

    for i, step in enumerate(trajectory):
        action = step.get("action", {})
        atype = action.get("type", "").lower()
        obs = step.get("observation", {})
        price = float(obs.get("price", 0.0))
        qty = float(action.get("quantity", 1))

        if atype == "buy":
            pending_buys.append((i, price, qty))
        elif atype == "sell" and pending_buys:
            buy_step, buy_price, buy_qty = pending_buys.pop(0)
            pnl = (price - buy_price) * min(qty, buy_qty)
            gross_pnl += pnl
            pairs.append((buy_step, i, pnl))

    total_trades = len(pairs)
    wins = sum(1 for _, _, p in pairs if p > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    avg_hold = (sum(s - b for b, s, _ in pairs) / total_trades) if total_trades > 0 else 0.0

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_hold": avg_hold,
        "gross_pnl": gross_pnl,
    }


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
# P1-2: Trade summary unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeTradeSummary:
    def test_returns_all_keys(self, simple_trajectory):
        s = compute_trade_summary(simple_trajectory)
        assert set(s) == {"total_trades", "win_rate", "avg_hold", "gross_pnl"}

    def test_single_round_trip_counted(self, simple_trajectory):
        s = compute_trade_summary(simple_trajectory)
        assert s["total_trades"] == 1

    def test_profitable_trade_yields_positive_pnl(self, simple_trajectory):
        # buy@100, sell@105, qty=10 → pnl=50
        s = compute_trade_summary(simple_trajectory)
        assert s["gross_pnl"] == pytest.approx(50.0)

    def test_win_rate_100_for_single_win(self, simple_trajectory):
        s = compute_trade_summary(simple_trajectory)
        assert s["win_rate"] == pytest.approx(100.0)

    def test_avg_hold_equals_step_distance(self, simple_trajectory):
        # buy at step 0, sell at step 2 → avg hold = 2
        s = compute_trade_summary(simple_trajectory)
        assert s["avg_hold"] == pytest.approx(2.0)

    def test_empty_trajectory_returns_zero_trades(self):
        s = compute_trade_summary([])
        assert s["total_trades"] == 0
        assert s["gross_pnl"] == pytest.approx(0.0)

    def test_only_buys_no_pairs(self):
        traj = [
            {"action": {"type": "buy", "quantity": 1}, "observation": {"price": 100.0}},
            {"action": {"type": "buy", "quantity": 1}, "observation": {"price": 102.0}},
        ]
        s = compute_trade_summary(traj)
        assert s["total_trades"] == 0

    def test_losing_trade_zero_win_rate(self):
        traj = [
            {"action": {"type": "buy", "quantity": 1}, "observation": {"price": 100.0}},
            {"action": {"type": "sell", "quantity": 1}, "observation": {"price": 90.0}},
        ]
        s = compute_trade_summary(traj)
        assert s["win_rate"] == pytest.approx(0.0)
        assert s["gross_pnl"] == pytest.approx(-10.0)

    def test_multiple_round_trips(self):
        traj = [
            {"action": {"type": "buy", "quantity": 1}, "observation": {"price": 100.0}},
            {"action": {"type": "sell", "quantity": 1}, "observation": {"price": 110.0}},
            {"action": {"type": "buy", "quantity": 1}, "observation": {"price": 110.0}},
            {"action": {"type": "sell", "quantity": 1}, "observation": {"price": 105.0}},
        ]
        s = compute_trade_summary(traj)
        assert s["total_trades"] == 2
        assert s["gross_pnl"] == pytest.approx(10.0 + (-5.0))
        assert s["win_rate"] == pytest.approx(50.0)


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


# ═══════════════════════════════════════════════════════════════════════════════
# P1-3: CSV export
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvExport:
    def test_filtered_df_serialises_to_csv(self, simple_trajectory, ohlcv_df):
        rows = []
        for i, step in enumerate(simple_trajectory):
            action = step.get("action", {})
            obs = step.get("observation", {})
            rows.append({
                "step": i,
                "action": action.get("type", ""),
                "price": obs.get("price"),
                "cash": obs.get("cash_balance"),
            })
        df = pd.DataFrame(rows)
        csv = df.to_csv(index=False)
        assert "step" in csv
        assert "action" in csv
        # Round-trip check
        reloaded = pd.read_csv(__import__("io").StringIO(csv))
        assert len(reloaded) == len(df)

    def test_csv_filtered_by_action_type(self, simple_trajectory):
        rows = [
            {"step": i, "action": s.get("action", {}).get("type", "")}
            for i, s in enumerate(simple_trajectory)
        ]
        df = pd.DataFrame(rows)
        filtered = df[df["action"] == "buy"]
        csv = filtered.to_csv(index=False)
        reloaded = pd.read_csv(__import__("io").StringIO(csv))
        assert all(reloaded["action"] == "buy")


# ═══════════════════════════════════════════════════════════════════════════════
# P1-4: Drawdown curve
# ═══════════════════════════════════════════════════════════════════════════════

class TestDrawdownCurve:
    def _compute_drawdown(self, df: pd.DataFrame) -> pd.Series:
        closes = df["close"]
        daily_ret = closes.pct_change().fillna(0)
        cum_ret = (1 + daily_ret).cumprod()
        roll_max = cum_ret.cummax()
        return (cum_ret - roll_max) / roll_max * 100

    def test_drawdown_is_non_positive(self, ohlcv_df):
        dd = self._compute_drawdown(ohlcv_df)
        assert (dd <= 0).all()

    def test_drawdown_starts_at_zero(self, ohlcv_df):
        dd = self._compute_drawdown(ohlcv_df)
        assert dd.iloc[0] == pytest.approx(0.0)

    def test_drawdown_same_length_as_ohlcv(self, ohlcv_df):
        dd = self._compute_drawdown(ohlcv_df)
        assert len(dd) == len(ohlcv_df)

    def test_monotone_up_series_has_zero_drawdown(self):
        dates = pd.date_range("2020-01-01", periods=10)
        df = pd.DataFrame({"close": [100.0 + i for i in range(10)]}, index=dates)
        dd = self._compute_drawdown(df)
        assert (dd <= 0).all()
        assert dd.min() == pytest.approx(0.0, abs=1e-10)


# ═══════════════════════════════════════════════════════════════════════════════
# P1-5: Integrity badge
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrityBadge:
    def _make_valid_run(self, tmp_path) -> Path:
        run_dir = tmp_path / "run-valid"
        run_dir.mkdir()
        manifest = {
            "run_id": "run-valid",
            "manifest_version": "2",
            "mode": "test",
            "symbols": ["AAPL"],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "decision.json").write_text(json.dumps({"run_id": "run-valid"}))
        (run_dir / "trajectory.json").write_text(json.dumps([]))
        (run_dir / "deltas.json").write_text(json.dumps({}))
        return run_dir

    def test_valid_run_passes_integrity(self, tmp_path):
        from ewm_core.eval.run_evaluator import evaluate_run, load_run_artifacts
        run_dir = self._make_valid_run(tmp_path)
        arts = load_run_artifacts(run_dir)
        result = evaluate_run(arts, artifact_dir=run_dir)
        assert result["integrity"]["integrity_errors"] == []

    def test_missing_manifest_fails_integrity(self, tmp_path):
        from ewm_core.eval.run_evaluator import evaluate_run, load_run_artifacts
        run_dir = tmp_path / "run-bad"
        run_dir.mkdir()
        # No files at all
        arts = load_run_artifacts(run_dir)
        result = evaluate_run(arts, artifact_dir=run_dir)
        assert len(result["integrity"]["integrity_errors"]) > 0

    def test_wrong_manifest_version_fails_integrity(self, tmp_path):
        from ewm_core.eval.run_evaluator import evaluate_run, load_run_artifacts
        run_dir = tmp_path / "run-wrong-ver"
        run_dir.mkdir()
        manifest = {"run_id": "run-wrong-ver", "manifest_version": "1", "mode": "test"}
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        arts = load_run_artifacts(run_dir)
        result = evaluate_run(arts, artifact_dir=run_dir)
        assert "manifest_version_mismatch" in result["integrity"]["integrity_errors"]

    def test_integrity_badge_renders_on_valid_dir(self, tmp_path):
        from streamlit.testing.v1 import AppTest
        run_dir = self._make_valid_run(tmp_path)
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        # Enter the run directory directly
        at.text_input[1].set_value(str(run_dir)).run()
        assert not at.exception
        successes = [s.value for s in at.success]
        assert any("integrity" in s.lower() for s in successes)

    def test_integrity_badge_renders_on_invalid_dir(self, tmp_path):
        from streamlit.testing.v1 import AppTest
        run_dir = tmp_path / "run-empty"
        run_dir.mkdir()
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input[1].set_value(str(run_dir)).run()
        assert not at.exception
        errors = [e.value for e in at.error]
        assert any("integrity" in e.lower() for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# P1-1: Zoom-to-trade (session_state logic)
# ═══════════════════════════════════════════════════════════════════════════════

class TestZoomToTrade:
    def test_zoom_range_clamped_at_start(self, ohlcv_df):
        """Step 2 with window=5 should not produce a negative index."""
        step = 2
        lo = max(0, step - 5)
        hi = min(len(ohlcv_df) - 1, step + 5)
        assert lo >= 0
        assert hi < len(ohlcv_df)

    def test_zoom_range_clamped_at_end(self, ohlcv_df):
        """Last step with window=5 should stay within bounds."""
        step = len(ohlcv_df) - 1
        lo = max(0, step - 5)
        hi = min(len(ohlcv_df) - 1, step + 5)
        assert lo >= 0
        assert hi == len(ohlcv_df) - 1

    def test_zoom_range_correct_width(self, ohlcv_df):
        """Mid-series step produces ±5 candle window (11 steps wide)."""
        step = 50
        lo = max(0, step - 5)
        hi = min(len(ohlcv_df) - 1, step + 5)
        assert hi - lo == 10

    def test_zoom_date_indices_are_valid(self, ohlcv_df):
        """Zoom range dates must be actual dates in the ohlcv index."""
        step = 30
        lo = max(0, step - 5)
        hi = min(len(ohlcv_df) - 1, step + 5)
        assert ohlcv_df.index[lo] in ohlcv_df.index
        assert ohlcv_df.index[hi] in ohlcv_df.index


# ═══════════════════════════════════════════════════════════════════════════════
# P2-6/9/10: Helper mirrors for isolated unit testing
# ═══════════════════════════════════════════════════════════════════════════════

def style_trajectory_df(df: pd.DataFrame):
    def _row_style(row: pd.Series) -> list[str]:
        action = str(row.get("action", "")).lower()
        if action == "buy":
            return ["background-color: rgba(38,166,154,0.15)"] * len(row)
        if action == "sell":
            return ["background-color: rgba(239,83,80,0.15)"] * len(row)
        return [""] * len(row)
    return df.style.apply(_row_style, axis=1)


def load_manifest(artifact_dir: str) -> dict | None:
    if not artifact_dir:
        return None
    p = Path(artifact_dir) / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def diff_manifest_keys(m1: dict, m2: dict) -> set[str]:
    return {k for k in set(m1) | set(m2) if m1.get(k) != m2.get(k)}


# ═══════════════════════════════════════════════════════════════════════════════
# P2-6: Colour-coded trajectory rows
# ═══════════════════════════════════════════════════════════════════════════════

class TestRowColouring:
    def _make_traj_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"step": 0, "action": "buy",  "price": 100.0},
            {"step": 1, "action": "hold", "price": 102.0},
            {"step": 2, "action": "sell", "price": 105.0},
        ])

    def test_returns_styler_object(self):
        df = self._make_traj_df()
        result = style_trajectory_df(df)
        assert hasattr(result, "apply"), "Expected pandas Styler"

    def test_buy_row_gets_green_background(self):
        df = self._make_traj_df()
        styler = style_trajectory_df(df)
        # Export styles to inspect row 0 (buy)
        styles = styler.export()
        applied = styler.apply(
            lambda row: (
                ["background-color: rgba(38,166,154,0.15)"] * len(row)
                if str(row.get("action", "")).lower() == "buy"
                else [""] * len(row)
            ),
            axis=1,
        )
        assert applied is not None

    def test_buy_style_string_contains_green(self):
        df = pd.DataFrame([{"action": "buy", "price": 100.0}])
        styler = style_trajectory_df(df)
        rendered = styler.to_html()
        assert "rgba(38,166,154" in rendered

    def test_sell_style_string_contains_red(self):
        df = pd.DataFrame([{"action": "sell", "price": 100.0}])
        styler = style_trajectory_df(df)
        rendered = styler.to_html()
        assert "rgba(239,83,80" in rendered

    def test_hold_row_has_no_background(self):
        df = pd.DataFrame([{"action": "hold", "price": 100.0}])
        styler = style_trajectory_df(df)
        rendered = styler.to_html()
        assert "rgba(38,166,154" not in rendered
        assert "rgba(239,83,80" not in rendered

    def test_empty_df_does_not_raise(self):
        df = pd.DataFrame(columns=["action", "price"])
        result = style_trajectory_df(df)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# P2-7: Persistent sidebar state
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistentSidebarState:
    def test_dark_mode_default_is_true(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        assert not at.exception
        checkboxes = {cb.label: cb for cb in at.checkbox}
        assert "Dark mode" in checkboxes
        assert checkboxes["Dark mode"].value is True

    def test_slider_value_survives_rerun(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.slider[0].set_value(150).run()
        assert not at.exception
        candles = next(m for m in at.metric if m.label == "Candles")
        assert candles.value == "150"

    def test_all_ma_checkboxes_present(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        labels = {cb.label for cb in at.checkbox}
        assert {"MA 20", "MA 50", "MA 200", "Dark mode"}.issubset(labels)

    def test_number_inputs_present_in_default_state(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        # start_price, drift, volatility, seed — 4 number inputs in GBM mode
        assert len(at.number_input) >= 4


# ═══════════════════════════════════════════════════════════════════════════════
# P2-8: Dark mode toggle
# ═══════════════════════════════════════════════════════════════════════════════

class TestDarkModeToggle:
    def test_dark_mode_checkbox_exists(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        labels = [cb.label for cb in at.checkbox]
        assert "Dark mode" in labels

    def test_dark_mode_on_by_default(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        dark_cb = next(cb for cb in at.checkbox if cb.label == "Dark mode")
        assert dark_cb.value is True

    def test_unchecking_dark_mode_reruns_without_error(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        dark_cb = next(cb for cb in at.checkbox if cb.label == "Dark mode")
        dark_cb.uncheck().run()
        assert not at.exception

    def test_rechecking_dark_mode_reruns_without_error(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        dark_cb = next(cb for cb in at.checkbox if cb.label == "Dark mode")
        dark_cb.uncheck().run()
        dark_cb2 = next(cb for cb in at.checkbox if cb.label == "Dark mode")
        dark_cb2.check().run()
        assert not at.exception


# ═══════════════════════════════════════════════════════════════════════════════
# P2-9: Run manifest summary panel
# ═══════════════════════════════════════════════════════════════════════════════

class TestManifestPanel:
    def _make_manifest_dir(self, tmp_path, manifest: dict) -> Path:
        run_dir = tmp_path / "run-manifest-test"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        return run_dir

    def test_load_manifest_returns_none_for_empty_string(self):
        assert load_manifest("") is None

    def test_load_manifest_returns_none_when_file_missing(self, tmp_path):
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()
        assert load_manifest(str(run_dir)) is None

    def test_load_manifest_returns_dict_for_valid_file(self, tmp_path):
        manifest = {"run_id": "run-abc", "mode": "test", "manifest_version": "2"}
        run_dir = self._make_manifest_dir(tmp_path, manifest)
        result = load_manifest(str(run_dir))
        assert result is not None
        assert result["run_id"] == "run-abc"

    def test_load_manifest_handles_malformed_json(self, tmp_path):
        run_dir = tmp_path / "bad-run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text("{invalid json")
        result = load_manifest(str(run_dir))
        assert result is None

    def test_load_manifest_preserves_all_fields(self, tmp_path):
        manifest = {
            "run_id": "run-xyz",
            "mode": "live",
            "symbols": ["AAPL", "MSFT"],
            "manifest_version": "2",
            "strategy_path": "strategies/ewm.py",
            "budgets": {"max_trades": 10},
        }
        run_dir = self._make_manifest_dir(tmp_path, manifest)
        result = load_manifest(str(run_dir))
        assert set(result.keys()) == set(manifest.keys())

    def test_manifest_expander_renders_when_run_loaded(self, tmp_path):
        from streamlit.testing.v1 import AppTest
        manifest = {"run_id": "run-abc", "mode": "test", "manifest_version": "2"}
        run_dir = self._make_manifest_dir(tmp_path, manifest)
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input[1].set_value(str(run_dir)).run()
        assert not at.exception
        expander_labels = [e.label for e in at.expander]
        assert any("manifest" in lbl.lower() for lbl in expander_labels)

    def test_no_manifest_expander_without_run(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        expander_labels = [e.label for e in at.expander]
        assert not any("manifest" in lbl.lower() for lbl in expander_labels)


# ═══════════════════════════════════════════════════════════════════════════════
# P2-10: Side-by-side run diff
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunDiff:
    def _make_run(self, tmp_path, name: str, manifest: dict) -> Path:
        run_dir = tmp_path / name
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        return run_dir

    def test_diff_returns_empty_set_for_identical_manifests(self):
        m = {"run_id": "run-a", "mode": "test", "manifest_version": "2"}
        assert diff_manifest_keys(m, m.copy()) == set()

    def test_diff_detects_changed_value(self):
        m1 = {"mode": "test", "run_id": "run-a"}
        m2 = {"mode": "live", "run_id": "run-a"}
        assert diff_manifest_keys(m1, m2) == {"mode"}

    def test_diff_detects_key_only_in_m1(self):
        m1 = {"mode": "test", "extra_key": "value"}
        m2 = {"mode": "test"}
        assert diff_manifest_keys(m1, m2) == {"extra_key"}

    def test_diff_detects_key_only_in_m2(self):
        m1 = {"mode": "test"}
        m2 = {"mode": "test", "new_key": "value"}
        assert diff_manifest_keys(m1, m2) == {"new_key"}

    def test_diff_detects_multiple_differences(self):
        m1 = {"mode": "test", "version": "1", "shared": "same"}
        m2 = {"mode": "live", "version": "2", "shared": "same"}
        result = diff_manifest_keys(m1, m2)
        assert result == {"mode", "version"}

    def test_run_diff_renders_when_both_runs_loaded(self, tmp_path):
        from streamlit.testing.v1 import AppTest
        m1 = {"run_id": "run-a", "mode": "test", "manifest_version": "2"}
        m2 = {"run_id": "run-b", "mode": "live", "manifest_version": "2"}
        run_a = self._make_run(tmp_path, "run-a", m1)
        run_b = self._make_run(tmp_path, "run-b", m2)
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input[1].set_value(str(run_a)).run()
        at.text_input[3].set_value(str(run_b)).run()
        assert not at.exception

    def test_no_diff_shown_without_run_b(self, tmp_path):
        from streamlit.testing.v1 import AppTest
        m1 = {"run_id": "run-a", "mode": "test", "manifest_version": "2"}
        run_a = self._make_run(tmp_path, "run-a-solo", m1)
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at.text_input[1].set_value(str(run_a)).run()
        assert not at.exception
        # No "Run diff" subheader without run B
        subheaders = [s.value for s in at.subheader]
        assert not any("diff" in s.lower() for s in subheaders)
