"""EWM-Core — Experiment page (P3-15: aggregate view over all runs)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from _shared import apply_theme, compute_run_return, init_session_state
from ewm_core.eval.experiment_evaluator import evaluate_experiment

init_session_state()
apply_theme()

st.title("EWM-Core Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Experiment")
    st.divider()
    experiment_root = st.text_input(
        "Experiment root",
        key="experiment_root",
        placeholder="/path/to/experiment/",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

st.subheader("Experiment")

if not experiment_root:
    st.info("Enter an experiment root directory in the sidebar.")
    st.stop()

_exp_path = Path(experiment_root)
if not _exp_path.exists():
    st.warning(f"Directory not found: {experiment_root}")
    st.stop()

with st.spinner("Evaluating experiment …"):
    try:
        result = evaluate_experiment(_exp_path)
    except Exception as e:
        st.error(f"Evaluation failed: {e}")
        st.stop()

agg = result["aggregate"]
summary = result["summary"]
runs = result["runs"]

# ── Aggregate metrics strip ───────────────────────────────────────────────────

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total runs",       agg["total_runs"])
m2.metric("OK runs",          summary["ok_runs"])
m3.metric("Failed runs",      summary["failed_runs"])
m4.metric("Integrity fail %", f"{agg['pct_integrity_fail']:.1f}%")
m5.metric(
    "Avg steps",
    f"{agg['avg_steps_executed']:.1f}" if agg["avg_steps_executed"] is not None else "—",
)

# ── Per-run table ─────────────────────────────────────────────────────────────

st.subheader("Per-run breakdown")

if runs:
    rows = []
    for r in runs:
        run_dir = _exp_path / r["run_id"]
        if not run_dir.exists():
            _sub = _exp_path / "artifacts" / r["run_id"]
            run_dir = _sub if _sub.exists() else run_dir
        period_return = compute_run_return(run_dir)
        rows.append({
            "run_id":          r["run_id"],
            "ok":              not r["integrity_errors"],
            "steps":           r["steps_executed"],
            "truncated":       r["truncated_by_budget"],
            "period_return_%": round(period_return, 2) if period_return is not None else None,
            "errors":          "; ".join(r["integrity_errors"]),
        })
    runs_df = pd.DataFrame(rows)

    def _style_runs(df: pd.DataFrame):
        def _row(row: pd.Series) -> list[str]:
            color = "rgba(38,166,154,0.12)" if row.get("ok") else "rgba(239,83,80,0.12)"
            return [f"background-color: {color}"] * len(row)
        return df.style.apply(_row, axis=1)

    st.dataframe(_style_runs(runs_df), width="stretch", hide_index=True)
else:
    st.info("No run directories found under the experiment root.")
