"""EWM-Core Streamlit dashboard — navigation entry point."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="EWM-Core", page_icon="📈", layout="wide")

pg = st.navigation([
    st.Page("pages/chart.py",      title="Chart",      icon="📈"),
    st.Page("pages/trajectory.py", title="Trajectory", icon="📋"),
    st.Page("pages/artifacts.py",  title="Artifacts",  icon="📁"),
    st.Page("pages/experiment.py", title="Experiment", icon="🔬"),
])
pg.run()
