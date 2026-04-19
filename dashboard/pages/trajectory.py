"""EWM-Core — Trajectory page (table, filter, CSV export, step detail)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from _shared import (
    apply_theme, compute_trade_summary, init_session_state,
    load_trajectory, style_trajectory_df,
)

init_session_state()
apply_theme()

st.title("EWM-Core Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Trajectory")
    st.divider()
    artifact_dir = st.text_input(
        "Run directory",
        key="artifact_dir",
        placeholder="/path/to/run-id/",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

st.subheader("Trajectory")

trajectory: list[dict] = []
if artifact_dir:
    trajectory = load_trajectory(artifact_dir)

if trajectory:
    summary = compute_trade_summary(trajectory)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Round trips",      summary["total_trades"])
    c2.metric("Win rate",         f"{summary['win_rate']:.1f}%")
    c3.metric("Avg hold (steps)", f"{summary['avg_hold']:.1f}")
    c4.metric("Gross P&L",        f"${summary['gross_pnl']:+.2f}")

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

    col_filter, col_export, _spacer = st.columns([2, 2, 3])
    with col_filter:
        action_filter = st.multiselect(
            "Filter by action",
            options=traj_df["action"].unique().tolist(),
            default=traj_df["action"].unique().tolist(),
        )
    filtered = traj_df[traj_df["action"].isin(action_filter)]

    with col_export:
        st.download_button(
            label="Download CSV",
            data=filtered.to_csv(index=False),
            file_name="trajectory.csv",
            mime="text/csv",
        )

    event = st.dataframe(
        style_trajectory_df(filtered),
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.get("rows", [])
    if selected_rows:
        idx = int(filtered.iloc[selected_rows[0]]["step"])
        st.session_state["zoom_step"] = idx
        with st.expander("Step detail", expanded=True):
            st.json(trajectory[idx])
else:
    st.info("No trajectory loaded. Select a run in the sidebar.")
