"""EWM-Core — Chart page (candlestick, metrics, trade summary, manifest diff)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import hashlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from _shared import (
    GBM_PRESETS, SS_DEFAULTS, TV_BORDER, TV_GREEN, TV_MUTED, TV_RED, TV_TEXT,
    apply_theme, compute_metrics, compute_run_return, compute_trade_summary,
    diff_manifest_keys, extract_pnl, extract_signals, get_colors, init_session_state,
    load_manifest, load_trajectory, style_trajectory_df,
)
from ewm_core.eval.run_evaluator import evaluate_run, load_run_artifacts
from ewm_core.market.synthetic import generate_ohlcv

init_session_state()
apply_theme()

# Hidden title for AppTest compatibility
st.title("EWM-Core Dashboard")

_C = get_colors()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### EWM-Core")
    st.divider()

    st.subheader("Agent mode")
    try:
        _has_llm = "DEMO_PASSWORD" in st.secrets
    except Exception:
        _has_llm = False
    _agent_options = ["Rule-based", "Claude LLM agent (demo)"] if _has_llm else ["Rule-based"]
    st.radio("Agent", options=_agent_options, key="agent_mode")

    if st.session_state.get("agent_mode") == "Claude LLM agent (demo)":
        if not st.session_state.get("llm_authenticated"):
            _pw = st.text_input("Demo password", type="password", key="_llm_pw_input")
            if _pw:
                try:
                    _ok = _pw == st.secrets["DEMO_PASSWORD"]
                except Exception:
                    _ok = False
                if _ok:
                    st.session_state["llm_authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        else:
            _calls = st.session_state.get("llm_calls_this_session", 0)
            if _calls <= 7:
                st.markdown(
                    f'<p style="color:#26a69a;font-size:11px;margin:2px 0;">Calls: {_calls} / 10</p>',
                    unsafe_allow_html=True,
                )
            elif _calls <= 9:
                st.markdown(
                    f'<p style="color:#ff9800;font-size:11px;margin:2px 0;">Calls: {_calls} / 10 — running low</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.error("Session limit reached (10/10). `pip install ewm-core[llm]` to run locally.")
            if _calls < 10:
                _ticker_missing = (
                    st.session_state.get("use_live", False)
                    and not st.session_state.get("ticker", "").strip()
                )
                def _trigger_llm():
                    st.session_state["llm_thinking"] = True

                st.button(
                    "Get Claude's decision",
                    key="llm_decide_btn",
                    on_click=_trigger_llm,
                    disabled=_ticker_missing,
                )
                if _ticker_missing:
                    st.caption("Enter a ticker above to enable.")

    st.divider()
    st.subheader("Data source")
    use_live = st.toggle("Live data (yfinance)", key="use_live")

    if use_live:
        ticker = st.text_input(
            "Ticker",
            key="ticker",
            placeholder="e.g. AMZN, MSFT, TSLA",
        ).strip().upper()

        # P3-12: Date range picker for live data
        st.subheader("Date range")
        import datetime
        _today = datetime.date.today()
        _default_start = _today - datetime.timedelta(days=90)
        date_range = st.date_input(
            "Range",
            value=(_default_start, _today),
            max_value=_today,
            key="date_range",
            label_visibility="collapsed",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            date_start, date_end = date_range
        else:
            date_start, date_end = _default_start, _today
    else:
        st.subheader("GBM parameters")

        # P3-13: Preset profiles
        preset_name = st.selectbox(
            "Profile",
            options=list(GBM_PRESETS.keys()),
            key="gbm_preset",
        )
        _prev = st.session_state.get("_prev_gbm_preset", "Custom")
        if preset_name != "Custom" and preset_name != _prev:
            _p = GBM_PRESETS[preset_name]
            st.session_state["drift"]     = _p["drift"]
            st.session_state["volatility"] = _p["volatility"]
        st.session_state["_prev_gbm_preset"] = preset_name

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
    dark_mode = st.checkbox("Dark mode", value=True, key="dark_mode")

    if not use_live:
        st.divider()
        st.subheader("Compare GBM")
        # P3-11: Second GBM path toggle
        compare_gbm = st.toggle("Overlay second path", key="compare_gbm")
        if compare_gbm:
            drift_b      = st.number_input("Drift B",      value=0.0003, format="%.4f", step=0.0001, key="drift_b")
            volatility_b = st.number_input("Volatility B", value=0.012,  format="%.4f", step=0.001,  key="volatility_b")
            seed_b       = st.number_input("Seed B", min_value=0, value=99, step=1, key="seed_b")
    else:
        compare_gbm = False

    st.divider()
    st.subheader("Run A")
    artifacts_root = st.text_input("Artifacts root", key="artifacts_root", placeholder="/path/to/artifacts/")
    artifact_dir: str = ""
    if artifacts_root:
        _root = Path(artifacts_root)
        if _root.exists():
            _run_dirs = sorted([d for d in _root.iterdir() if d.is_dir()],
                               key=lambda d: d.stat().st_mtime, reverse=True)
            if _run_dirs:
                _sel = st.selectbox("Run", options=[d.name for d in _run_dirs], key="run_select_a")
                artifact_dir = str(_root / _sel)
            else:
                st.info("No run subdirectories found.")
        else:
            st.warning("Directory not found.")
    else:
        artifact_dir = st.text_input("Or enter run directory directly",
                                     key="artifact_dir", placeholder="/path/to/run-id/")

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

    st.divider()
    st.subheader("Run B (compare)")
    artifacts_root_b = st.text_input("Compare artifacts root", key="artifacts_root_b",
                                     placeholder="/path/to/artifacts/")
    artifact_dir_b: str = ""
    if artifacts_root_b:
        _root_b = Path(artifacts_root_b)
        if _root_b.exists():
            _run_dirs_b = sorted([d for d in _root_b.iterdir() if d.is_dir()],
                                 key=lambda d: d.stat().st_mtime, reverse=True)
            if _run_dirs_b:
                _sel_b = st.selectbox("Compare run", options=[d.name for d in _run_dirs_b],
                                      key="run_select_b")
                artifact_dir_b = str(_root_b / _sel_b)
            else:
                st.info("No run subdirectories found.")
        else:
            st.warning("Directory not found.")
    else:
        artifact_dir_b = st.text_input("Or enter compare run directory",
                                       key="artifact_dir_b", placeholder="/path/to/run-id/")

# ── Market data ───────────────────────────────────────────────────────────────


@st.cache_data(ttl=300)
def _fetch_live(ticker: str, start: str, end: str) -> pd.DataFrame:
    for attempt in range(2):
        try:
            raw = yf.download(ticker, start=start, end=end,
                              auto_adjust=True, progress=False)
            if raw is not None and not raw.empty:
                break
        except Exception:
            if attempt == 1:
                return pd.DataFrame()
    else:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() for c in raw.columns]
    else:
        raw.columns = [c.lower() for c in raw.columns]
    return raw[["open", "high", "low", "close", "volume"]]


@st.cache_data
def _fetch_synthetic(n: int, sp: float, d: float, v: float, s: int) -> pd.DataFrame:
    return generate_ohlcv(n_candles=n, drift=d, volatility=v, seed=s, start_price=sp)


# ── Chart header ──────────────────────────────────────────────────────────────

_hdr_col, _tf_col = st.columns([3, 5])

with _hdr_col:
    if use_live:
        st.markdown(
            f'<div class="tv-chart-header"><span class="tv-symbol-label">{ticker}</span>'
            f'<span class="tv-source-badge">Live</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="tv-chart-header"><span class="tv-symbol-label">Synthetic GBM</span>'
            '<span class="tv-source-badge">Simulated</span></div>',
            unsafe_allow_html=True,
        )

with _tf_col:
    if use_live:
        pass  # date range picker already in sidebar
    else:
        st.markdown(
            f'<p style="color:#787b86;font-size:11px;padding-top:10px;">'
            f"drift {drift:+.4f} · vol {volatility:.4f} · seed {seed}</p>",
            unsafe_allow_html=True,
        )

# ── Fetch primary data ────────────────────────────────────────────────────────

if use_live:
    with st.spinner(f"Fetching {ticker} …"):
        ohlcv = _fetch_live(ticker, str(date_start), str(date_end))
    if ohlcv.empty:
        st.error(
            f"Could not fetch data for '{ticker}'. "
            "Note: AAPL is rate-limited on Streamlit Cloud. "
            "Try AMZN, MSFT, TSLA, or BTC-USD instead, "
            "or switch to synthetic data."
        )
        st.session_state["llm_thinking"] = False
        st.stop()
    chart_title = f"{ticker}  ·  {date_start} → {date_end}"
else:
    ohlcv = _fetch_synthetic(n_candles, start_price, drift, volatility, seed)
    chart_title = f"Synthetic GBM  ·  {len(ohlcv)} candles  ·  seed {seed}"

# ── Clear stale LLM result when market params change ─────────────────────────

if use_live:
    _phash = hashlib.md5(
        f"{st.session_state.get('ticker')}:{st.session_state.get('date_range')}".encode()
    ).hexdigest()
else:
    _phash = hashlib.md5(
        f"{n_candles}:{start_price}:{drift}:{volatility}:{seed}".encode()
    ).hexdigest()

if _phash != st.session_state.get("llm_params_hash", ""):
    st.session_state["llm_last_decision"] = None
    st.session_state["llm_params_hash"] = _phash

# P3-11: Fetch second GBM path (normalised)
ohlcv_b: pd.DataFrame | None = None
if compare_gbm and not use_live:
    ohlcv_b = _fetch_synthetic(n_candles, start_price, drift_b, volatility_b, seed_b)

# ── Metrics strip ─────────────────────────────────────────────────────────────

metrics = compute_metrics(ohlcv)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Period return",   f"{metrics['total_return']:+.2f}%")
m2.metric("Max drawdown",    f"{metrics['max_drawdown']:.2f}%")
m3.metric("Ann. volatility", f"{metrics['annualised_vol']:.1f}%")
m4.metric("Sharpe (ann.)",   f"{metrics['sharpe']:.2f}")
m5.metric("Candles",         len(ohlcv))

# ── Trajectory & trade summary ────────────────────────────────────────────────

trajectory: list[dict] = []
if artifact_dir:
    trajectory = load_trajectory(artifact_dir)

buy_signals, sell_signals = extract_signals(trajectory, ohlcv)
pnl_series = extract_pnl(trajectory)

if trajectory:
    summary = compute_trade_summary(trajectory)
    with st.expander("Trade summary", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Round trips",      summary["total_trades"])
        c2.metric("Win rate",         f"{summary['win_rate']:.1f}%")
        c3.metric("Avg hold (steps)", f"{summary['avg_hold']:.1f}")
        c4.metric("Gross P&L",        f"${summary['gross_pnl']:+.2f}")

# P2-9: Manifest panel
manifest_a = load_manifest(artifact_dir)
if manifest_a:
    _PRIORITY = ["run_id", "mode", "symbols", "manifest_version", "strategy_path", "budgets"]
    with st.expander("Run manifest", expanded=False):
        _ordered = [(k, manifest_a[k]) for k in _PRIORITY if k in manifest_a]
        _other   = [(k, v) for k, v in manifest_a.items() if k not in _PRIORITY]
        _mcols   = st.columns(2)
        for _i, (_k, _v) in enumerate(_ordered + _other):
            _mcols[_i % 2].markdown(f"**{_k}**: `{_v}`")

# P2-10: Run diff
manifest_b = load_manifest(artifact_dir_b)
if manifest_a and manifest_b:
    st.subheader("Run diff")
    _diff_keys = diff_manifest_keys(manifest_a, manifest_b)
    _all_keys  = sorted(set(manifest_a) | set(manifest_b))
    _dcol_a, _dcol_b = st.columns(2)
    with _dcol_a:
        st.markdown(f"**Run A** — `{artifact_dir}`")
        for _k in _all_keys:
            _val   = manifest_a.get(_k, "—")
            _color = TV_RED if _k in _diff_keys else TV_TEXT
            st.markdown(f'<span style="color:{_color}">**{_k}**: `{_val}`</span>',
                        unsafe_allow_html=True)
    with _dcol_b:
        st.markdown(f"**Run B** — `{artifact_dir_b}`")
        for _k in _all_keys:
            _val   = manifest_b.get(_k, "—")
            _color = TV_RED if _k in _diff_keys else TV_TEXT
            st.markdown(f'<span style="color:{_color}">**{_k}**: `{_val}`</span>',
                        unsafe_allow_html=True)

# ── Chart ─────────────────────────────────────────────────────────────────────

closes       = ohlcv["close"]
_daily_ret   = closes.pct_change().fillna(0)
_cum_ret     = (1 + _daily_ret).cumprod()
_roll_max    = _cum_ret.cummax()
drawdown_pct = (_cum_ret - _roll_max) / _roll_max * 100

has_pnl = not pnl_series.empty

fig = make_subplots(
    rows=3, cols=1, shared_xaxes=True,
    row_heights=[0.62, 0.17, 0.21],
    vertical_spacing=0.0,
    specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]],
)

fig.add_trace(
    go.Candlestick(
        x=ohlcv.index, open=ohlcv["open"], high=ohlcv["high"],
        low=ohlcv["low"], close=ohlcv["close"], name="Price",
        increasing=dict(line=dict(color=TV_GREEN, width=1), fillcolor=TV_GREEN),
        decreasing=dict(line=dict(color=TV_RED,   width=1), fillcolor=TV_RED),
        whiskerwidth=0.3,
    ),
    row=1, col=1, secondary_y=False,
)

# P3-11: Normalised second GBM path
if ohlcv_b is not None:
    _norm_a = ohlcv["close"] / ohlcv["close"].iloc[0] * 100
    _norm_b = ohlcv_b["close"] / ohlcv_b["close"].iloc[0] * 100
    fig.add_trace(
        go.Scatter(x=ohlcv.index, y=_norm_a, name="Path A (norm)",
                   line=dict(color="#2962ff", width=1.5), opacity=0.85,
                   hovertemplate="Path A %{y:.2f}<extra></extra>"),
        row=1, col=1, secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(x=ohlcv_b.index[:len(ohlcv)], y=_norm_b[:len(ohlcv)], name="Path B (norm)",
                   line=dict(color="#ff9800", width=1.5), opacity=0.85,
                   hovertemplate="Path B %{y:.2f}<extra></extra>"),
        row=1, col=1, secondary_y=True,
    )

for _window, _color, _enabled in [(20, "#2962ff", show_ma20), (50, "#ff9800", show_ma50), (200, "#9c27b0", show_ma200)]:
    if _enabled and len(ohlcv) >= _window:
        _ma = ohlcv["close"].rolling(_window).mean()
        fig.add_trace(
            go.Scatter(x=ohlcv.index, y=_ma, name=f"MA {_window}",
                       line=dict(color=_color, width=1.5), opacity=0.9),
            row=1, col=1, secondary_y=False,
        )

if not buy_signals.empty:
    fig.add_trace(
        go.Scatter(x=ohlcv.index[buy_signals.index], y=buy_signals.values * 0.965,
                   mode="markers",
                   marker=dict(symbol="triangle-up", size=10, color=TV_GREEN,
                               line=dict(color=TV_GREEN, width=1)),
                   name="Buy", hovertemplate="Buy @ %{y:.2f}<extra></extra>"),
        row=1, col=1, secondary_y=False,
    )

if not sell_signals.empty:
    fig.add_trace(
        go.Scatter(x=ohlcv.index[sell_signals.index], y=sell_signals.values * 1.035,
                   mode="markers",
                   marker=dict(symbol="triangle-down", size=10, color=TV_RED,
                               line=dict(color=TV_RED, width=1)),
                   name="Sell", hovertemplate="Sell @ %{y:.2f}<extra></extra>"),
        row=1, col=1, secondary_y=False,
    )

if has_pnl:
    fig.add_trace(
        go.Scatter(x=ohlcv.index[pnl_series.index], y=pnl_series.values,
                   name="Cash", line=dict(color="#ff9800", width=1.5), opacity=0.85,
                   hovertemplate="Cash $%{y:,.2f}<extra></extra>"),
        row=1, col=1, secondary_y=True,
    )

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

fig.add_trace(
    go.Scatter(x=ohlcv.index, y=drawdown_pct, name="Drawdown",
               fill="tozeroy", line=dict(color=TV_RED, width=1),
               fillcolor="rgba(239,83,80,0.15)", showlegend=False,
               hovertemplate="%{y:.2f}%<extra>Drawdown</extra>"),
    row=3, col=1,
)

_axis = dict(
    gridcolor=_C["grid"], gridwidth=1, linecolor=_C["border"],
    tickfont=dict(color=_C["muted"], size=10),
    showspikes=True, spikecolor=_C["muted"], spikethickness=1,
    spikedash="dot", spikemode="across", showgrid=True, zeroline=False,
)
_legend_bg = (
    f"rgba({int(_C['panel'][1:3],16)},{int(_C['panel'][3:5],16)},{int(_C['panel'][5:7],16)},0.75)"
    if len(_C["panel"]) == 7 else "rgba(30,34,45,0.75)"
)

fig.update_layout(
    title=dict(text=chart_title, font=dict(color=_C["text"], size=13), x=0.0, xanchor="left"),
    paper_bgcolor=_C["bg"], plot_bgcolor=_C["bg"],
    font=dict(color=_C["text"], family="Trebuchet MS, Arial, sans-serif", size=11),
    xaxis_rangeslider_visible=False, height=680,
    margin=dict(l=10, r=80, t=40, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=_C["panel"], bordercolor=_C["border"],
                    font=dict(color=_C["text"], size=11)),
    legend=dict(orientation="v", x=0.01, y=0.99, xanchor="left", yanchor="top",
                bgcolor=_legend_bg, bordercolor=_C["border"], borderwidth=1,
                font=dict(color=_C["text"], size=11)),
    modebar=dict(bgcolor=_C["panel"], color=_C["muted"], activecolor=_C["text"], orientation="v"),
    dragmode="pan",
)

for _r in [1, 2, 3]:
    fig.update_xaxes(**_axis, row=_r, col=1)
fig.update_xaxes(showticklabels=False, row=1, col=1)
fig.update_xaxes(showticklabels=False, row=2, col=1)
fig.update_xaxes(showticklabels=True,  row=3, col=1)

fig.update_yaxes(**_axis, title_text="Price",
                 title_font=dict(color=_C["muted"], size=10),
                 side="right", row=1, col=1, secondary_y=False)
if has_pnl or ohlcv_b is not None:
    _sec_title = "Norm (100)" if ohlcv_b is not None else "Cash ($)"
    _sec_color = "#2962ff"   if ohlcv_b is not None else "#ff9800"
    fig.update_yaxes(**_axis, title_text=_sec_title,
                     title_font=dict(color=_sec_color, size=10),
                     side="left", row=1, col=1, secondary_y=True)
fig.update_yaxes(**_axis, title_text="Vol",  title_font=dict(color=_C["muted"], size=10), side="right", row=2, col=1)
fig.update_yaxes(**_axis, title_text="DD %", title_font=dict(color=TV_RED, size=10),     side="right", row=3, col=1)

for _r in [1, 2]:
    fig.update_xaxes(showline=True, linewidth=1, linecolor=_C["border"], row=_r, col=1)

if st.session_state.get("zoom_step") is not None:
    _step = st.session_state["zoom_step"]
    _lo   = max(0, _step - 5)
    _hi   = min(len(ohlcv) - 1, _step + 5)
    fig.update_xaxes(range=[str(ohlcv.index[_lo]), str(ohlcv.index[_hi])])

# ── LLM agent panel ───────────────────────────────────────────────────────────

if st.session_state.get("agent_mode") == "Claude LLM agent (demo)":
    _last = st.session_state.get("llm_last_decision")
    _badge_col, _reason_col = st.columns([1, 4])
    with _badge_col:
        if _last:
            _action = _last.get("type", "hold")
            _color  = TV_GREEN if _action == "buy" else TV_RED if _action == "sell" else TV_MUTED
            st.markdown(
                f'<div style="background:{_color};color:#fff;font-size:13px;font-weight:700;'
                f'padding:6px 14px;border-radius:4px;text-align:center;letter-spacing:1px;">'
                f'{_action.upper()}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#2a2e39;color:#787b86;font-size:12px;'
                'padding:6px 14px;border-radius:4px;text-align:center;">—</div>',
                unsafe_allow_html=True,
            )
    with _reason_col:
        if _last:
            st.markdown(
                f'<p style="color:#d1d4dc;font-size:12px;margin:4px 0 0;">'
                f'{_last.get("reasoning", "")}</p>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p style="color:#787b86;font-size:12px;font-style:italic;margin:4px 0 0;">'
                "Click 'Get Claude\\'s decision' to analyse the current market</p>",
                unsafe_allow_html=True,
            )

st.plotly_chart(fig, width="stretch", config={
    "displayModeBar": True, "displaylogo": False, "scrollZoom": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "ewm_chart"},
})

# ── LLM agent decision button ─────────────────────────────────────────────────

if st.session_state.get("agent_mode") == "Claude LLM agent (demo)":
    if not st.session_state.get("llm_authenticated"):
        st.info("Enter the demo password in the sidebar to enable the LLM agent.")
    elif st.session_state.get("llm_calls_this_session", 0) >= 10:
        st.warning("Session limit reached. `pip install ewm-core[llm]` to run locally.")
    else:
        try:
            from ewm_core.agents.llm_agent import LLMAgent  # noqa: PLC0415
            _symbol = ticker if (use_live and ticker) else "SYN"
            _sma5   = float(ohlcv["close"].rolling(5).mean().iloc[-1])
            _sma10  = float(ohlcv["close"].rolling(10).mean().iloc[-1])
            _obs = {
                "symbol":   _symbol,
                "price":    float(ohlcv["close"].iloc[-1]),
                "sma5":     _sma5,
                "sma10":    _sma10,
                "volume":   float(ohlcv["volume"].iloc[-1]),
                "position": "flat",
            }
            _thinking = st.session_state.get("llm_thinking", False)

            if _thinking:
                with st.spinner("Claude is thinking..."):
                    try:
                        _api_key = st.secrets.get("ANTHROPIC_API_KEY")
                    except Exception:
                        _api_key = None
                    try:
                        _agent = LLMAgent(api_key=_api_key)
                        _result = _agent.decide(_obs)
                        st.session_state["llm_last_decision"] = _result
                        st.session_state["llm_calls_this_session"] = (
                            st.session_state.get("llm_calls_this_session", 0) + 1
                        )
                    except Exception as exc:
                        st.error(f"LLM call failed: {exc}")
                    finally:
                        st.session_state["llm_thinking"] = False
                st.rerun()
        except ImportError:
            st.info(
                "LLM agent not available in this deployment. "
                "`pip install ewm-core[llm]` to enable."
            )
