"""Shared utilities for EWM-Core dashboard pages."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ── TradingView color palette ──────────────────────────────────────────────────
TV_BG     = "#131722"
TV_PANEL  = "#1e222d"
TV_GRID   = "#1e222d"
TV_BORDER = "#2a2e39"
TV_TEXT   = "#d1d4dc"
TV_MUTED  = "#787b86"
TV_GREEN  = "#26a69a"
TV_RED    = "#ef5350"

# ── P3-13: Preset GBM profiles ────────────────────────────────────────────────
GBM_PRESETS: dict[str, dict | None] = {
    "Custom":         None,
    "Low vol":        {"drift": 0.0001, "volatility": 0.005},
    "Trending":       {"drift": 0.0008, "volatility": 0.010},
    "Mean-reverting": {"drift": -0.0002, "volatility": 0.015},
}

# ── Session state defaults ─────────────────────────────────────────────────────
SS_DEFAULTS: dict = {
    "use_live":           False,
    "ticker":             "AMZN",
    "n_candles":          200,
    "start_price":        100.0,
    "drift":              0.0003,
    "volatility":         0.012,
    "seed":               42,
    "show_ma20":          True,
    "show_ma50":          True,
    "show_ma200":         False,
    "dark_mode":          True,
    "artifacts_root":     "",
    "artifact_dir":       "",
    "artifacts_root_b":   "",
    "artifact_dir_b":     "",
    "compare_gbm":        False,
    "drift_b":            0.0003,
    "volatility_b":       0.012,
    "seed_b":             99,
    "gbm_preset":         "Custom",
    "_prev_gbm_preset":   "Custom",
    "experiment_root":    "",
    "zoom_step":          None,
    "agent_mode":             "Rule-based",
    "llm_authenticated":      False,
    "llm_calls_this_session": 0,
    "llm_last_decision":      None,
    "llm_thinking":           False,
    "llm_params_hash":        "",
}


def init_session_state() -> None:
    for k, v in SS_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def ensure_ticker_default() -> None:
    """Ensure ticker is never empty in session state."""
    if not st.session_state.get("ticker", "").strip():
        st.session_state["ticker"] = "AMZN"


def get_colors() -> dict:
    dark = bool(st.session_state.get("dark_mode", True))
    return {
        "bg":     TV_BG     if dark else "#ffffff",
        "panel":  TV_PANEL  if dark else "#f5f5f5",
        "grid":   TV_GRID   if dark else "#f0f0f0",
        "border": TV_BORDER if dark else "#d0d0d0",
        "text":   TV_TEXT   if dark else "#131722",
        "muted":  TV_MUTED  if dark else "#555555",
    }


THEME_CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"] { background-color: #131722; color: #d1d4dc; }
[data-testid="stMainBlockContainer"] > div > div:first-child h1 { display: none; }
[data-testid="stHeader"] { background-color: #1e222d !important; border-bottom: 1px solid #2a2e39; }
section[data-testid="stSidebar"] > div { background-color: #1e222d; border-right: 1px solid #2a2e39; }
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span { color: #d1d4dc !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #d1d4dc !important; }
h1, h2, h3, p, span, label { color: #d1d4dc; }
h1 { font-size: 20px !important; font-weight: 700; letter-spacing: 0.3px; }
[data-testid="stSubheader"] {
    color: #787b86 !important; font-size: 11px !important;
    text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
    border-bottom: 1px solid #2a2e39; padding-bottom: 6px;
}
[data-testid="stMetric"] { background-color: #1e222d; border: 1px solid #2a2e39; border-radius: 4px; padding: 10px 16px; }
[data-testid="stMetricLabel"] p { color: #787b86 !important; font-size: 10px !important; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
[data-testid="stMetricValue"] { color: #d1d4dc !important; font-size: 18px !important; font-weight: 600; font-family: "Trebuchet MS", monospace; }
.stTextInput input, .stNumberInput input { background-color: #2a2e39 !important; color: #d1d4dc !important; border: 1px solid #363c4e !important; border-radius: 3px; }
.stSelectbox div[data-baseweb="select"] { background-color: #2a2e39; border: 1px solid #363c4e; }
.stSelectbox div[data-baseweb="select"] > div { color: #d1d4dc; background-color: #2a2e39; }
[data-testid="stPills"] > div { gap: 2px; flex-wrap: nowrap; }
[data-testid="stPills"] button { background-color: #2a2e39 !important; color: #787b86 !important; border: 1px solid #363c4e !important; border-radius: 3px !important; padding: 3px 12px !important; font-size: 12px !important; font-weight: 600 !important; min-height: unset !important; height: 28px !important; transition: all 0.12s; }
[data-testid="stPills"] button:hover { background-color: #363c4e !important; color: #d1d4dc !important; }
[data-testid="stPills"] button[aria-checked="true"] { background-color: #2962ff !important; color: #ffffff !important; border-color: #2962ff !important; }
.stCheckbox label span, .stToggle label span { color: #d1d4dc !important; }
.stSlider [data-testid="stMarkdownContainer"] p { color: #787b86 !important; font-size: 11px; }
hr { border-color: #2a2e39 !important; margin: 6px 0; }
.stSuccess > div { background-color: #0d1f0d; border-left: 3px solid #26a69a !important; color: #26a69a; border-radius: 3px; }
.stError   > div { background-color: #1f0d0d; border-left: 3px solid #ef5350 !important; color: #ef5350; border-radius: 3px; }
.stWarning > div { background-color: #1f1a0d; border-left: 3px solid #ff9800 !important; color: #ff9800; border-radius: 3px; }
.stInfo    > div { background-color: #0d111f; border-left: 3px solid #2962ff !important; color: #787b86; border-radius: 3px; }
[data-testid="stExpander"] summary { background-color: #1e222d; color: #d1d4dc; border: 1px solid #2a2e39; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; }
[data-testid="stExpander"] > div > div { background-color: #1e222d; border: 1px solid #2a2e39; border-top: none; border-radius: 0 0 4px 4px; }
.stDataFrame { border: 1px solid #2a2e39; border-radius: 4px; overflow: hidden; }
.stButton button, .stDownloadButton button { background-color: #2a2e39; color: #d1d4dc; border: 1px solid #363c4e; border-radius: 3px; font-size: 12px; }
.stButton button:hover, .stDownloadButton button:hover { background-color: #363c4e; color: #ffffff; }
.tv-chart-header { display: flex; align-items: center; gap: 16px; padding: 8px 0 4px; border-bottom: 1px solid #2a2e39; margin-bottom: 4px; }
.tv-symbol-label { font-size: 18px; font-weight: 700; color: #d1d4dc; letter-spacing: 0.2px; }
.tv-source-badge { font-size: 11px; color: #787b86; background: #2a2e39; border: 1px solid #363c4e; border-radius: 3px; padding: 2px 8px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


# ── Data helpers ───────────────────────────────────────────────────────────────

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
        if daily_returns.std() else 0.0
    )
    return {"total_return": total_return, "max_drawdown": max_drawdown,
            "annualised_vol": vol, "sharpe": sharpe}


def load_trajectory(path: str) -> list[dict]:
    traj_path = Path(path) / "trajectory.json"
    if not traj_path.exists():
        return []
    try:
        return json.loads(traj_path.read_text())
    except Exception:
        return []


def extract_signals(trajectory: list[dict], ohlcv: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
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
    return {"total_trades": total_trades, "win_rate": win_rate,
            "avg_hold": avg_hold, "gross_pnl": gross_pnl}


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


def style_trajectory_df(df: pd.DataFrame):
    def _row_style(row: pd.Series) -> list[str]:
        action = str(row.get("action", "")).lower()
        if action == "buy":
            return ["background-color: rgba(38,166,154,0.15)"] * len(row)
        if action == "sell":
            return ["background-color: rgba(239,83,80,0.15)"] * len(row)
        return [""] * len(row)
    return df.style.apply(_row_style, axis=1)


def compute_run_return(run_dir: Path) -> float | None:
    """Compute period return from trajectory price observations."""
    traj = load_trajectory(str(run_dir))
    prices = [
        float(s["observation"]["price"])
        for s in traj
        if s.get("observation", {}).get("price") is not None
    ]
    if len(prices) < 2:
        return None
    return (prices[-1] / prices[0] - 1) * 100
