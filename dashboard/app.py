"""EWM-Core Streamlit dashboard — TradingView-inspired UI."""

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

st.set_page_config(page_title="EWM-Core", page_icon="📈", layout="wide")

# ── Session state defaults (P2-7: persistent sidebar state) ──────────────────

_SS_DEFAULTS: dict = {
    "use_live": False,
    "ticker": "AAPL",
    "n_candles": 200,
    "start_price": 100.0,
    "drift": 0.0003,
    "volatility": 0.012,
    "seed": 42,
    "show_ma20": True,
    "show_ma50": True,
    "show_ma200": False,
    "dark_mode": True,
    "artifacts_root": "",
    "artifact_dir": "",
    "artifacts_root_b": "",
    "artifact_dir_b": "",
}
for _k, _v in _SS_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── TradingView color palette ─────────────────────────────────────────────────

_TV_BG     = "#131722"
_TV_PANEL  = "#1e222d"
_TV_GRID   = "#1e222d"
_TV_BORDER = "#2a2e39"
_TV_TEXT   = "#d1d4dc"
_TV_MUTED  = "#787b86"
_TV_GREEN  = "#26a69a"
_TV_RED    = "#ef5350"

# P2-8: chart colors swap with dark mode
_dark = bool(st.session_state["dark_mode"])
_C_BG     = _TV_BG     if _dark else "#ffffff"
_C_PANEL  = _TV_PANEL  if _dark else "#f5f5f5"
_C_GRID   = _TV_GRID   if _dark else "#f0f0f0"
_C_BORDER = _TV_BORDER if _dark else "#d0d0d0"
_C_TEXT   = _TV_TEXT   if _dark else "#131722"
_C_MUTED  = _TV_MUTED  if _dark else "#555555"

# ── TradingView dark theme (CSS) ──────────────────────────────────────────────

st.markdown(
    """
<style>
/* ── Base ── */
.stApp, [data-testid="stAppViewContainer"] { background-color: #131722; color: #d1d4dc; }
/* Hide the AppTest-required title from visible UI */
[data-testid="stMainBlockContainer"] > div > div:first-child h1 { display: none; }
[data-testid="stHeader"] { background-color: #1e222d !important; border-bottom: 1px solid #2a2e39; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div {
    background-color: #1e222d;
    border-right: 1px solid #2a2e39;
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span { color: #d1d4dc !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #d1d4dc !important; }

/* ── Typography ── */
h1, h2, h3, p, span, label { color: #d1d4dc; }
h1 { font-size: 20px !important; font-weight: 700; letter-spacing: 0.3px; }
[data-testid="stSubheader"] {
    color: #787b86 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
    border-bottom: 1px solid #2a2e39;
    padding-bottom: 6px;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background-color: #1e222d;
    border: 1px solid #2a2e39;
    border-radius: 4px;
    padding: 10px 16px;
}
[data-testid="stMetricLabel"] p {
    color: #787b86 !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    color: #d1d4dc !important;
    font-size: 18px !important;
    font-weight: 600;
    font-family: "Trebuchet MS", monospace;
}

/* ── Inputs ── */
.stTextInput input, .stNumberInput input {
    background-color: #2a2e39 !important;
    color: #d1d4dc !important;
    border: 1px solid #363c4e !important;
    border-radius: 3px;
}
.stSelectbox div[data-baseweb="select"] { background-color: #2a2e39; border: 1px solid #363c4e; }
.stSelectbox div[data-baseweb="select"] > div { color: #d1d4dc; background-color: #2a2e39; }

/* ── Pills / timeframe bar ── */
[data-testid="stPills"] > div { gap: 2px; flex-wrap: nowrap; }
[data-testid="stPills"] button {
    background-color: #2a2e39 !important;
    color: #787b86 !important;
    border: 1px solid #363c4e !important;
    border-radius: 3px !important;
    padding: 3px 12px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    min-height: unset !important;
    height: 28px !important;
    transition: all 0.12s;
}
[data-testid="stPills"] button:hover { background-color: #363c4e !important; color: #d1d4dc !important; }
[data-testid="stPills"] button[aria-checked="true"] {
    background-color: #2962ff !important;
    color: #ffffff !important;
    border-color: #2962ff !important;
}

/* ── Checkboxes / toggles ── */
.stCheckbox label span, .stToggle label span { color: #d1d4dc !important; }

/* ── Slider ── */
.stSlider [data-testid="stMarkdownContainer"] p { color: #787b86 !important; font-size: 11px; }

/* ── Divider ── */
hr { border-color: #2a2e39 !important; margin: 6px 0; }

/* ── Alerts ── */
.stSuccess > div { background-color: #0d1f0d; border-left: 3px solid #26a69a !important; color: #26a69a; border-radius: 3px; }
.stError   > div { background-color: #1f0d0d; border-left: 3px solid #ef5350 !important; color: #ef5350; border-radius: 3px; }
.stWarning > div { background-color: #1f1a0d; border-left: 3px solid #ff9800 !important; color: #ff9800; border-radius: 3px; }
.stInfo    > div { background-color: #0d111f; border-left: 3px solid #2962ff !important; color: #787b86; border-radius: 3px; }

/* ── Expander ── */
[data-testid="stExpander"] summary {
    background-color: #1e222d;
    color: #d1d4dc;
    border: 1px solid #2a2e39;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
[data-testid="stExpander"] > div > div {
    background-color: #1e222d;
    border: 1px solid #2a2e39;
    border-top: none;
    border-radius: 0 0 4px 4px;
}

/* ── DataFrame ── */
.stDataFrame { border: 1px solid #2a2e39; border-radius: 4px; overflow: hidden; }

/* ── Buttons ── */
.stButton button, .stDownloadButton button {
    background-color: #2a2e39;
    color: #d1d4dc;
    border: 1px solid #363c4e;
    border-radius: 3px;
    font-size: 12px;
}
.stButton button:hover, .stDownloadButton button:hover {
    background-color: #363c4e;
    color: #ffffff;
}

/* ── Chart container ── */
.tv-chart-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 4px;
    border-bottom: 1px solid #2a2e39;
    margin-bottom: 4px;
}
.tv-symbol-label {
    font-size: 18px;
    font-weight: 700;
    color: #d1d4dc;
    letter-spacing: 0.2px;
}
.tv-source-badge {
    font-size: 11px;
    color: #787b86;
    background: #2a2e39;
    border: 1px solid #363c4e;
    border-radius: 3px;
    padding: 2px 8px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
</style>
""",
    unsafe_allow_html=True,
)

# Hidden title for AppTest compatibility — visually suppressed by CSS
st.title("EWM-Core Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### EWM-Core")
    st.divider()

    st.subheader("Data source")
    use_live = st.toggle("Live data (yfinance)", key="use_live")

    if use_live:
        ticker = st.text_input("Ticker", key="ticker").strip().upper()
    else:
        st.subheader("GBM parameters")
        n_candles   = st.slider("Candles", 50, 500, 200, step=10, key="n_candles")
        start_price = st.number_input("Start price", min_value=1.0, value=100.0, step=1.0, key="start_price")
        drift       = st.number_input("Drift (daily)", value=0.0003, format="%.4f", step=0.0001, key="drift")
        volatility  = st.number_input("Volatility (daily)", value=0.012, format="%.4f", step=0.001, key="volatility")
        seed        = st.number_input("Seed", min_value=0, value=42, step=1, key="seed")

    st.divider()
    st.subheader("Overlays")
    show_ma20  = st.checkbox("MA 20",  value=True,  key="show_ma20")
    show_ma50  = st.checkbox("MA 50",  value=True,  key="show_ma50")
    show_ma200 = st.checkbox("MA 200", value=False, key="show_ma200")

    st.divider()
    st.subheader("Display")
    # P2-8: Dark mode toggle — persists in session state
    dark_mode = st.checkbox("Dark mode", value=True, key="dark_mode")

    st.divider()
    st.subheader("Run A")
    artifacts_root = st.text_input(
        "Artifacts root", key="artifacts_root", placeholder="/path/to/artifacts/"
    )
    run_id: str | None = None
    artifact_dir: str = ""

    if artifacts_root:
        _root = Path(artifacts_root)
        if _root.exists():
            _run_dirs = sorted(
                [d for d in _root.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if _run_dirs:
                _selected = st.selectbox("Run", options=[d.name for d in _run_dirs])
                artifact_dir = str(_root / _selected)
                run_id = _selected
            else:
                st.info("No run subdirectories found.")
        else:
            st.warning("Directory not found.")
    else:
        artifact_dir = st.text_input(
            "Or enter run directory directly",
            key="artifact_dir",
            placeholder="/path/to/run-id/",
        )

    # Integrity badge — Run A
    if artifact_dir and Path(artifact_dir).exists():
        try:
            _arts = load_run_artifacts(Path(artifact_dir))
            _eval = evaluate_run(_arts, artifact_dir=Path(artifact_dir))
            _errs = _eval["integrity"]["integrity_errors"]
            if not _errs:
                st.success("Integrity: PASS")
            else:
                st.error(f"Integrity: FAIL ({len(_errs)} error(s))")
        except Exception:
            st.warning("Integrity: could not evaluate")

    # P2-10: Run B selector ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Run B (compare)")
    artifacts_root_b = st.text_input(
        "Compare artifacts root", key="artifacts_root_b", placeholder="/path/to/artifacts/"
    )
    artifact_dir_b: str = ""

    if artifacts_root_b:
        _root_b = Path(artifacts_root_b)
        if _root_b.exists():
            _run_dirs_b = sorted(
                [d for d in _root_b.iterdir() if d.is_dir()],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if _run_dirs_b:
                _selected_b = st.selectbox("Compare run", options=[d.name for d in _run_dirs_b])
                artifact_dir_b = str(_root_b / _selected_b)
            else:
                st.info("No run subdirectories found.")
        else:
            st.warning("Directory not found.")
    else:
        artifact_dir_b = st.text_input(
            "Or enter compare run directory",
            key="artifact_dir_b",
            placeholder="/path/to/run-id/",
        )

# ── Market data helpers ───────────────────────────────────────────────────────


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


# ── Chart header bar (TradingView-style) ──────────────────────────────────────

_hdr_col, _tf_col = st.columns([3, 5])

with _hdr_col:
    if use_live:
        st.markdown(
            f'<div class="tv-chart-header">'
            f'<span class="tv-symbol-label">{ticker}</span>'
            f'<span class="tv-source-badge">Live</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="tv-chart-header">'
            '<span class="tv-symbol-label">Synthetic GBM</span>'
            '<span class="tv-source-badge">Simulated</span>'
            "</div>",
            unsafe_allow_html=True,
        )

with _tf_col:
    if use_live:
        period = st.pills(
            "Period",
            options=["1mo", "3mo", "6mo", "1y", "2y"],
            default="3mo",
            label_visibility="collapsed",
        )
        if period is None:
            period = "3mo"
    else:
        st.markdown(
            f'<p style="color:#787b86;font-size:11px;padding-top:10px;">'
            f"drift {drift:+.4f} · vol {volatility:.4f} · seed {seed}"
            f"</p>",
            unsafe_allow_html=True,
        )

# ── Fetch data ────────────────────────────────────────────────────────────────

if use_live:
    with st.spinner(f"Fetching {ticker} …"):
        ohlcv = _fetch_live(ticker, period)
    if ohlcv.empty:
        st.error(f"No data returned for {ticker}. Check the ticker symbol.")
        st.stop()
    chart_title = f"{ticker}  ·  {period}"
else:
    ohlcv = _fetch_synthetic(n_candles, start_price, drift, volatility, seed)
    chart_title = f"Synthetic GBM  ·  {len(ohlcv)} candles  ·  seed {seed}"

# ── Metrics strip ─────────────────────────────────────────────────────────────


def _compute_metrics(df: pd.DataFrame) -> dict:
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


metrics = _compute_metrics(ohlcv)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Period return",  f"{metrics['total_return']:+.2f}%")
m2.metric("Max drawdown",   f"{metrics['max_drawdown']:.2f}%")
m3.metric("Ann. volatility", f"{metrics['annualised_vol']:.1f}%")
m4.metric("Sharpe (ann.)",  f"{metrics['sharpe']:.2f}")
m5.metric("Candles",        len(ohlcv))

# ── Trajectory helpers ────────────────────────────────────────────────────────


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
    cash: dict[int, float] = {}
    for i, step in enumerate(trajectory):
        obs = step.get("observation", {})
        bal = obs.get("cash_balance")
        if bal is not None:
            cash[i] = float(bal)
    return pd.Series(cash, dtype=float)


def _compute_trade_summary(trajectory: list[dict]) -> dict:
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


# P2-9: Manifest loader
def _load_manifest(artifact_dir: str) -> dict | None:
    if not artifact_dir:
        return None
    p = Path(artifact_dir) / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# P2-10: Manifest differ
def _diff_manifest_keys(m1: dict, m2: dict) -> set[str]:
    return {k for k in set(m1) | set(m2) if m1.get(k) != m2.get(k)}


# P2-6: Row colouring
def _style_trajectory_df(df: pd.DataFrame):
    def _row_style(row: pd.Series) -> list[str]:
        action = str(row.get("action", "")).lower()
        if action == "buy":
            return ["background-color: rgba(38,166,154,0.15)"] * len(row)
        if action == "sell":
            return ["background-color: rgba(239,83,80,0.15)"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


trajectory: list[dict] = []
if artifact_dir:
    trajectory = _load_trajectory(artifact_dir)

buy_signals, sell_signals = _extract_signals(trajectory, ohlcv)
pnl_series = _extract_pnl(trajectory)

# Trade summary card
if trajectory:
    summary = _compute_trade_summary(trajectory)
    with st.expander("Trade summary", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Round trips",        summary["total_trades"])
        c2.metric("Win rate",           f"{summary['win_rate']:.1f}%")
        c3.metric("Avg hold (steps)",   f"{summary['avg_hold']:.1f}")
        c4.metric("Gross P&L",          f"${summary['gross_pnl']:+.2f}")

# ── P2-9: Manifest summary panel ─────────────────────────────────────────────

manifest_a = _load_manifest(artifact_dir)
if manifest_a:
    _MANIFEST_PRIORITY = ["run_id", "mode", "symbols", "manifest_version", "strategy_path", "budgets"]
    with st.expander("Run manifest", expanded=False):
        _ordered = [(k, manifest_a[k]) for k in _MANIFEST_PRIORITY if k in manifest_a]
        _other   = [(k, v) for k, v in manifest_a.items() if k not in _MANIFEST_PRIORITY]
        _all_fields = _ordered + _other
        _mcols = st.columns(2)
        for _i, (_k, _v) in enumerate(_all_fields):
            _mcols[_i % 2].markdown(f"**{_k}**: `{_v}`")

# ── P2-10: Side-by-side run diff ─────────────────────────────────────────────

manifest_b = _load_manifest(artifact_dir_b)
if manifest_a and manifest_b:
    st.subheader("Run diff")
    _diff_keys = _diff_manifest_keys(manifest_a, manifest_b)
    _all_keys  = sorted(set(manifest_a) | set(manifest_b))
    _dcol_a, _dcol_b = st.columns(2)
    with _dcol_a:
        st.markdown(f"**Run A** — `{artifact_dir}`")
        for _k in _all_keys:
            _val = manifest_a.get(_k, "—")
            _color = _TV_RED if _k in _diff_keys else _TV_TEXT
            st.markdown(
                f'<span style="color:{_color}">**{_k}**: `{_val}`</span>',
                unsafe_allow_html=True,
            )
    with _dcol_b:
        st.markdown(f"**Run B** — `{artifact_dir_b}`")
        for _k in _all_keys:
            _val = manifest_b.get(_k, "—")
            _color = _TV_RED if _k in _diff_keys else _TV_TEXT
            st.markdown(
                f'<span style="color:{_color}">**{_k}**: `{_val}`</span>',
                unsafe_allow_html=True,
            )

# ── Chart ─────────────────────────────────────────────────────────────────────

# Drawdown series
closes = ohlcv["close"]
_daily_ret  = closes.pct_change().fillna(0)
_cum_ret    = (1 + _daily_ret).cumprod()
_roll_max   = _cum_ret.cummax()
drawdown_pct = (_cum_ret - _roll_max) / _roll_max * 100

has_pnl = not pnl_series.empty

fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.62, 0.17, 0.21],
    vertical_spacing=0.0,
    specs=[
        [{"secondary_y": True}],
        [{"secondary_y": False}],
        [{"secondary_y": False}],
    ],
)

# Row 1: Candlesticks
fig.add_trace(
    go.Candlestick(
        x=ohlcv.index,
        open=ohlcv["open"],
        high=ohlcv["high"],
        low=ohlcv["low"],
        close=ohlcv["close"],
        name="Price",
        increasing=dict(line=dict(color=_TV_GREEN, width=1), fillcolor=_TV_GREEN),
        decreasing=dict(line=dict(color=_TV_RED,   width=1), fillcolor=_TV_RED),
        whiskerwidth=0.3,
    ),
    row=1, col=1, secondary_y=False,
)

# Moving averages
for _window, _color, _enabled in [(20, "#2962ff", show_ma20), (50, "#ff9800", show_ma50), (200, "#9c27b0", show_ma200)]:
    if _enabled and len(ohlcv) >= _window:
        _ma = ohlcv["close"].rolling(_window).mean()
        fig.add_trace(
            go.Scatter(x=ohlcv.index, y=_ma, name=f"MA {_window}",
                       line=dict(color=_color, width=1.5), opacity=0.9),
            row=1, col=1, secondary_y=False,
        )

# Buy/sell signal markers
if not buy_signals.empty:
    fig.add_trace(
        go.Scatter(
            x=ohlcv.index[buy_signals.index],
            y=buy_signals.values * 0.965,
            mode="markers",
            marker=dict(symbol="triangle-up", size=10, color=_TV_GREEN,
                        line=dict(color=_TV_GREEN, width=1)),
            name="Buy",
            hovertemplate="Buy @ %{y:.2f}<extra></extra>",
        ),
        row=1, col=1, secondary_y=False,
    )

if not sell_signals.empty:
    fig.add_trace(
        go.Scatter(
            x=ohlcv.index[sell_signals.index],
            y=sell_signals.values * 1.035,
            mode="markers",
            marker=dict(symbol="triangle-down", size=10, color=_TV_RED,
                        line=dict(color=_TV_RED, width=1)),
            name="Sell",
            hovertemplate="Sell @ %{y:.2f}<extra></extra>",
        ),
        row=1, col=1, secondary_y=False,
    )

# P&L curve on secondary y-axis
if has_pnl:
    fig.add_trace(
        go.Scatter(
            x=ohlcv.index[pnl_series.index],
            y=pnl_series.values,
            name="Cash",
            line=dict(color="#ff9800", width=1.5),
            opacity=0.85,
            hovertemplate="Cash $%{y:,.2f}<extra></extra>",
        ),
        row=1, col=1, secondary_y=True,
    )

# Row 2: Volume
_vol_colors = [
    "rgba(38,166,154,0.6)" if c >= o else "rgba(239,83,80,0.6)"
    for c, o in zip(ohlcv["close"], ohlcv["open"])
]
fig.add_trace(
    go.Bar(x=ohlcv.index, y=ohlcv["volume"], name="Volume",
           marker_color=_vol_colors, showlegend=False,
           hovertemplate="%{y:,.0f}<extra>Vol</extra>"),
    row=2, col=1,
)

# Row 3: Drawdown
fig.add_trace(
    go.Scatter(
        x=ohlcv.index,
        y=drawdown_pct,
        name="Drawdown",
        fill="tozeroy",
        line=dict(color=_TV_RED, width=1),
        fillcolor="rgba(239,83,80,0.15)",
        showlegend=False,
        hovertemplate="%{y:.2f}%<extra>Drawdown</extra>",
    ),
    row=3, col=1,
)

# ── Chart layout ──────────────────────────────────────────────────────────────

_axis_common = dict(
    gridcolor=_C_GRID,
    gridwidth=1,
    linecolor=_C_BORDER,
    tickfont=dict(color=_C_MUTED, size=10),
    showspikes=True,
    spikecolor=_C_MUTED,
    spikethickness=1,
    spikedash="dot",
    spikemode="across",
    showgrid=True,
    zeroline=False,
)

fig.update_layout(
    title=dict(text=chart_title, font=dict(color=_C_TEXT, size=13), x=0.0, xanchor="left"),
    paper_bgcolor=_C_BG,
    plot_bgcolor=_C_BG,
    font=dict(color=_C_TEXT, family="Trebuchet MS, Arial, sans-serif", size=11),
    xaxis_rangeslider_visible=False,
    height=680,
    margin=dict(l=10, r=80, t=40, b=10),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor=_C_PANEL,
        bordercolor=_C_BORDER,
        font=dict(color=_C_TEXT, size=11),
    ),
    legend=dict(
        orientation="v",
        x=0.01,
        y=0.99,
        xanchor="left",
        yanchor="top",
        bgcolor=f"rgba({int(_C_PANEL[1:3],16)},{int(_C_PANEL[3:5],16)},{int(_C_PANEL[5:7],16)},0.75)" if len(_C_PANEL) == 7 else "rgba(30,34,45,0.75)",
        bordercolor=_C_BORDER,
        borderwidth=1,
        font=dict(color=_C_TEXT, size=11),
    ),
    modebar=dict(
        bgcolor=_C_PANEL,
        color=_C_MUTED,
        activecolor=_C_TEXT,
        orientation="v",
    ),
    dragmode="pan",
)

# X-axes
for _r in [1, 2, 3]:
    fig.update_xaxes(**_axis_common, row=_r, col=1)
fig.update_xaxes(showticklabels=False, row=1, col=1)
fig.update_xaxes(showticklabels=False, row=2, col=1)
fig.update_xaxes(showticklabels=True,  row=3, col=1)

# Y-axes — price on RIGHT (TV convention)
fig.update_yaxes(**_axis_common, title_text="Price",
                 title_font=dict(color=_C_MUTED, size=10),
                 side="right", row=1, col=1, secondary_y=False)
if has_pnl:
    fig.update_yaxes(**_axis_common, title_text="Cash ($)",
                     title_font=dict(color="#ff9800", size=10),
                     side="left", row=1, col=1, secondary_y=True)
fig.update_yaxes(**_axis_common, title_text="Vol",
                 title_font=dict(color=_C_MUTED, size=10),
                 side="right", row=2, col=1)
fig.update_yaxes(**_axis_common, title_text="DD %",
                 title_font=dict(color=_TV_RED, size=10),
                 side="right", row=3, col=1)

# Subplot separator lines
for _r in [1, 2]:
    fig.update_xaxes(showline=True, linewidth=1, linecolor=_C_BORDER, row=_r, col=1)

# P1-1: Zoom-to-trade
if "zoom_step" in st.session_state:
    _step = st.session_state["zoom_step"]
    _lo   = max(0, _step - 5)
    _hi   = min(len(ohlcv) - 1, _step + 5)
    fig.update_xaxes(range=[str(ohlcv.index[_lo]), str(ohlcv.index[_hi])])

st.plotly_chart(
    fig,
    width="stretch",
    config={
        "displayModeBar": True,
        "displaylogo": False,
        "scrollZoom": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
        "toImageButtonOptions": {"format": "png", "filename": "ewm_chart"},
    },
)

# ── Trajectory table ──────────────────────────────────────────────────────────

st.subheader("Trajectory")

if trajectory:
    rows = []
    for i, step in enumerate(trajectory):
        action = step.get("action", {})
        obs    = step.get("observation", {})
        rows.append({
            "step":     i,
            "symbol":   action.get("symbol", obs.get("symbol", "")),
            "action":   action.get("type", ""),
            "price":    obs.get("price"),
            "cash":     obs.get("cash_balance"),
            "quantity": action.get("quantity"),
            "reason":   action.get("reason", ""),
        })
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

    # P2-6: Color-coded rows
    event = st.dataframe(
        _style_trajectory_df(filtered),
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.get("rows", [])
    if selected_rows:
        idx = int(filtered.iloc[selected_rows[0]]["step"])
        st.session_state["zoom_step"] = idx
        st.json(trajectory[idx])
else:
    st.info("No trajectory loaded. Select a run in the sidebar.")

# ── Artifact viewer ───────────────────────────────────────────────────────────

st.subheader("Artifact viewer")

if artifact_dir:
    _apath = Path(artifact_dir)
    if not _apath.exists():
        st.warning(f"Directory not found: {artifact_dir}")
    else:
        _artifact_files = sorted(_apath.glob("*.json"))
        if not _artifact_files:
            st.info("No JSON files found in the artifact directory.")
        else:
            _sel_file = st.selectbox("File", options=_artifact_files, format_func=lambda p: p.name)
            try:
                st.json(json.loads(_sel_file.read_text()))
            except Exception as e:
                st.error(f"Failed to parse {_sel_file.name}: {e}")
else:
    st.info("Provide an artifacts root or run directory in the sidebar.")
