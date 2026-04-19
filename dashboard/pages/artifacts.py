"""EWM-Core — Artifacts page (JSON file viewer)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from _shared import apply_theme, init_session_state

init_session_state()
apply_theme()

st.title("EWM-Core Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Artifacts")
    st.divider()
    artifact_dir = st.text_input(
        "Run directory",
        key="artifact_dir",
        placeholder="/path/to/run-id/",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

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
            _sel_file = st.selectbox(
                "File",
                options=_artifact_files,
                format_func=lambda p: p.name,
            )
            try:
                _content = json.loads(_sel_file.read_text())
                st.json(_content)
            except Exception as e:
                st.error(f"Failed to parse {_sel_file.name}: {e}")
else:
    st.info("Provide an artifacts root or run directory in the sidebar.")
