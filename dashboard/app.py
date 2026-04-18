"""EWM-Core Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from ewm_core.eval.run_evaluator import evaluate_run, load_run_artifacts
from ewm_core.market.synthetic import generate_ohlcv

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EWM-Core Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("EWM-Core Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Data source")
    use_live = st.toggle("Live data (yfinance)", value=False)

    if use_live:
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
    else:
        st.subheader("Synthetic GBM parameters")
        n_candles = st.slider("Candles", 50, 500, 200, step=10)
        start_price = st.number_input("Start price", min_value=1.0, value=100.0, step=1.0)
        drift = st.number_input("Drift (daily)", value=0.0003, format="%.4f", step=0.0001)
        volatility = st.number_input("Volatility (daily)", value=0.012, format="%.4f", step=0.001)
        seed = st.number_input("Seed", min_value=0, value=42, step=1)

    st.divider()
    st.subheader("Overlays")
    show_ma20 = st.checkbox("MA 20", value=True)
    show_ma50 = st.checkbox("MA 50", value=True)
    show_ma200 = st.checkbox("MA 200", value=False)

    st.divider()
    st.header("Run selector")
    artifacts_root = st.text_input("Artifacts root", placeholder="/path/to/artifacts/")
    run_id: str | None = None
    artifact_dir: str = ""

    if artifacts_root:
        root_path = Path(artifacts_root)
        if root_path.exists():
            run_dirs = sorted(
                [d for d in root_path.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if run_dirs:
                run_labels = [d.name for d in run_dirs]
                selected_run = st.selectbox("Run", options=run_labels)
                artifact_dir = str(root_path / selected_run)
                run_id = selected_run
            else:
                st.info("No run subdirectories found.")
        else:
            st.warning("Directory not found.")
    else:
        artifact_dir = st.text_input(
            "Or enter run directory directly", placeholder="/path/to/run-id/"
        )

    # P1-5: Integrity check badge
    if artifact_dir and Path(artifact_dir).exists():
        try:
            _arts = load_run_artifacts(Path(artifact_dir))
            _eval = evaluate_run(_arts, artifact_dir=Path(artifact_dir))
            _errors = _eval["integrity"]["integrity_errors"]
            if not _errors:
                st.success("Integrity: PASS")
            else:
                st.error(f"Integrity: FAIL ({len(_errors)} error(s))")
        except Exception:
            st.warning("Integrity: could not evaluate")

# ── Market data ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _fetch_live(ticker: str, period: str) -> pd.DataFrame:
    raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() for c in raw.columns]
    else:
        raw.columns = [c.lower() for c in raw.columns]
    return raw[["open", "high", "low", "close", "volume"]]


@st.cache_data
def _fetch_synthetic(
    n_candles: int, start_price: float, drift: float, volatility: float, seed: int
) -> pd.DataFrame:
    return generate_ohlcv(
        n_candles=n_candles,
        drift=drift,
        volatility=volatility,
        seed=seed,
        start_price=start_price,
    )


if use_live:
    with st.spinner(f"Fetching {ticker} …"):
        ohlcv = _fetch_live(ticker, period)
    if ohlcv.empty:
        st.error(f"No data returned for {ticker}. Check the ticker symbol.")
        st.stop()
    chart_title = f"{ticker} — {period} (live)"
else:
    ohlcv = _fetch_synthetic(n_candles, start_price, drift, volatility, seed)
    chart_title = f"Synthetic GBM — {len(ohlcv)} candles (seed={seed})"

# ── Metrics ───────────────────────────────────────────────────────────────────

def _compute_metrics(df: pd.DataFrame) -> dict:
    closes = df["close"]
    total_return = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
    daily_returns = closes.pct_change().dropna()
    cumulative = (1 + daily_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100
    vol = daily_returns.std() * np.sqrt(252) * 100
    sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() else 0.0
    return {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "annualised_vol": vol,
        "sharpe": sharpe,
    }

metrics = _compute_metrics(ohlcv)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Period return", f"{metrics['total_return']:+.2f}%")
m2.metric("Max drawdown", f"{metrics['max_drawdown']:.2f}%")
m3.metric("Ann. volatility", f"{metrics['annualised_vol']:.1f}%")
m4.metric("Sharpe (ann.)", f"{metrics['sharpe']:.2f}")
m5.metric("Candles", len(ohlcv))

# ── Load trajectory ───────────────────────────────────────────────────────────

def _load_trajectory(path: str) -> list[dict]:
    traj_path = Path(path) / "trajectory.json"
    if not traj_path.exists():
        return []
    try:
        return json.loads(traj_path.read_text())
    except Exception:
        return []


def _extract_signals(
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


def _extract_pnl(trajectory: list[dict]) -> pd.Series:
    """Extract cash_balance series from trajectory observations."""
    cash: dict[int, float] = {}
    for i, step in enumerate(trajectory):
        obs = step.get("observation", {})
        bal = obs.get("cash_balance")
        if bal is not None:
            cash[i] = float(bal)
    return pd.Series(cash, dtype=float)


# P1-2: Trade summary helper
def _compute_trade_summary(trajectory: list[dict]) -> dict:
    """Compute trade-level summary stats via FIFO buy/sell pairing."""
    pending_buys: list[tuple[int, float, float]] = []  # (step, price, qty)
    pairs: list[tuple[int, int, float]] = []  # (buy_step, sell_step, pnl)
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


trajectory: list[dict] = []
if artifact_dir:
    trajectory = _load_trajectory(artifact_dir)

buy_signals, sell_signals = _extract_signals(trajectory, ohlcv)
pnl_series = _extract_pnl(trajectory)

# P1-2: Trade summary card (shown only when a run is loaded)
if trajectory:
    summary = _compute_trade_summary(trajectory)
    with st.expander("Trade summary", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Round trips", summary["total_trades"])
        c2.metric("Win rate", f"{summary['win_rate']:.1f}%")
        c3.metric("Avg hold (steps)", f"{summary['avg_hold']:.1f}")
        c4.metric("Gross P&L", f"${summary['gross_pnl']:+.2f}")

# ── Chart ─────────────────────────────────────────────────────────────────────

has_pnl = not pnl_series.empty

# P1-4: Drawdown series
closes = ohlcv["close"]
daily_ret = closes.pct_change().fillna(0)
cum_ret = (1 + daily_ret).cumprod()
roll_max = cum_ret.cummax()
drawdown_pct = (cum_ret - roll_max) / roll_max * 100

fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.60, 0.20, 0.20],
    vertical_spacing=0.02,
    specs=[
        [{"secondary_y": True}],
        [{"secondary_y": False}],
        [{"secondary_y": False}],
    ],
)

# Candlesticks
fig.add_trace(
    go.Candlestick(
        x=ohlcv.index,
        open=ohlcv["open"],
        high=ohlcv["high"],
        low=ohlcv["low"],
        close=ohlcv["close"],
        name="OHLCV",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ),
    row=1, col=1, secondary_y=False,
)

# Moving averages
ma_configs = [
    (20, "#1976d2", show_ma20),
    (50, "#f57c00", show_ma50),
    (200, "#7b1fa2", show_ma200),
]
for window, color, enabled in ma_configs:
    if enabled and len(ohlcv) >= window:
        ma = ohlcv["close"].rolling(window).mean()
        fig.add_trace(
            go.Scatter(
                x=ohlcv.index,
                y=ma,
                name=f"MA{window}",
                line=dict(color=color, width=1.5, dash="dot"),
                opacity=0.85,
            ),
            row=1, col=1, secondary_y=False,
        )

# Buy / sell markers
if not buy_signals.empty:
    fig.add_trace(
        go.Scatter(
            x=ohlcv.index[buy_signals.index],
            y=buy_signals.values * 0.98,
            mode="markers",
            marker=dict(symbol="triangle-up", size=12, color="#26a69a"),
            name="Buy",
        ),
        row=1, col=1, secondary_y=False,
    )

if not sell_signals.empty:
    fig.add_trace(
        go.Scatter(
            x=ohlcv.index[sell_signals.index],
            y=sell_signals.values * 1.02,
            mode="markers",
            marker=dict(symbol="triangle-down", size=12, color="#ef5350"),
            name="Sell",
        ),
        row=1, col=1, secondary_y=False,
    )

# P&L curve on secondary y-axis
if has_pnl:
    pnl_dates = ohlcv.index[pnl_series.index]
    fig.add_trace(
        go.Scatter(
            x=pnl_dates,
            y=pnl_series.values,
            name="Cash balance",
            line=dict(color="#ff9800", width=2),
            opacity=0.9,
        ),
        row=1, col=1, secondary_y=True,
    )

# Volume subplot
volume_colors = [
    "#26a69a" if c >= o else "#ef5350"
    for c, o in zip(ohlcv["close"], ohlcv["open"])
]
fig.add_trace(
    go.Bar(
        x=ohlcv.index,
        y=ohlcv["volume"],
        name="Volume",
        marker_color=volume_colors,
        showlegend=False,
    ),
    row=2, col=1,
)

# P1-4: Drawdown subplot
fig.add_trace(
    go.Scatter(
        x=ohlcv.index,
        y=drawdown_pct,
        name="Drawdown",
        fill="tozeroy",
        line=dict(color="#ef5350", width=1),
        fillcolor="rgba(239,83,80,0.2)",
        showlegend=False,
    ),
    row=3, col=1,
)

fig.update_layout(
    title=chart_title,
    xaxis_rangeslider_visible=False,
    height=650,
    margin=dict(l=0, r=0, t=40, b=0),
    template="plotly_white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
if has_pnl:
    fig.update_yaxes(title_text="Cash ($)", row=1, col=1, secondary_y=True)
fig.update_yaxes(title_text="Volume", row=2, col=1)
fig.update_yaxes(title_text="Drawdown %", row=3, col=1)

# P1-1: Zoom-to-trade — apply stored zoom range to chart
zoom_range: list | None = None
if "zoom_step" in st.session_state:
    step = st.session_state["zoom_step"]
    lo = max(0, step - 5)
    hi = min(len(ohlcv) - 1, step + 5)
    zoom_range = [str(ohlcv.index[lo]), str(ohlcv.index[hi])]
    fig.update_xaxes(range=zoom_range)

st.plotly_chart(fig, width="stretch")

# ── Trajectory table ──────────────────────────────────────────────────────────

st.subheader("Trajectory")

if trajectory:
    rows = []
    for i, step in enumerate(trajectory):
        action = step.get("action", {})
        obs = step.get("observation", {})
        rows.append(
            {
                "step": i,
                "symbol": action.get("symbol", obs.get("symbol", "")),
                "action": action.get("type", ""),
                "price": obs.get("price"),
                "cash": obs.get("cash_balance"),
                "quantity": action.get("quantity"),
                "reason": action.get("reason", ""),
            }
        )
    traj_df = pd.DataFrame(rows)

    col_filter, col_export, col_spacer = st.columns([2, 2, 3])
    with col_filter:
        action_filter = st.multiselect(
            "Filter by action",
            options=traj_df["action"].unique().tolist(),
            default=traj_df["action"].unique().tolist(),
        )
    filtered = traj_df[traj_df["action"].isin(action_filter)]

    # P1-3: CSV export
    with col_export:
        st.download_button(
            label="Download CSV",
            data=filtered.to_csv(index=False),
            file_name="trajectory.csv",
            mime="text/csv",
        )

    event = st.dataframe(
        filtered,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.get("rows", [])
    if selected_rows:
        idx = int(filtered.iloc[selected_rows[0]]["step"])
        # P1-1: Store selected step for zoom-to-trade on next rerun
        st.session_state["zoom_step"] = idx
        st.json(trajectory[idx])
else:
    st.info("No trajectory loaded. Select a run in the sidebar.")

# ── Artifact JSON viewer ──────────────────────────────────────────────────────

st.subheader("Artifact viewer")

if artifact_dir:
    artifact_path = Path(artifact_dir)
    if not artifact_path.exists():
        st.warning(f"Directory not found: {artifact_dir}")
    else:
        artifact_files = sorted(artifact_path.glob("*.json"))
        if not artifact_files:
            st.info("No JSON files found in the artifact directory.")
        else:
            selected_file = st.selectbox(
                "File", options=artifact_files, format_func=lambda p: p.name
            )
            try:
                content = json.loads(selected_file.read_text())
                st.json(content)
            except Exception as e:
                st.error(f"Failed to parse {selected_file.name}: {e}")
else:
    st.info("Provide an artifacts root or run directory in the sidebar.")
