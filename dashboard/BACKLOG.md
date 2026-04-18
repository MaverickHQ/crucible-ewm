# Dashboard Feature Backlog

Prioritised by impact-to-effort ratio for the ewm-core Phase 1 dashboard.
Items marked ✅ are already implemented.

---

## Implemented
- ✅ Candlestick chart with buy/sell signal markers
- ✅ Volume subplot (colour-coded)
- ✅ MA20 / MA50 / MA200 overlays (toggleable)
- ✅ P&L / cash-balance curve on secondary y-axis
- ✅ Run selector (browse subdirectories from artifacts root)
- ✅ Trajectory table with action filter and row selection
- ✅ Artifact JSON file viewer
- ✅ Metrics row: period return, max drawdown, ann. volatility, Sharpe, candles
- ✅ Live data toggle via yfinance
- ✅ Synthetic GBM parameter controls

---

## Backlog

### P1 — High impact, low effort

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Zoom-to-trade** | Clicking a trajectory row sets the chart x-range to ±5 candles around that step via `st.session_state` + `fig.update_xaxes(range=...)` |
| 2 | **Trade summary card** | When a run is loaded: total trades, win rate, avg hold, gross P&L. Sits between metrics row and chart. |
| 3 | **CSV export** | `st.download_button` on the filtered trajectory table. One line of code. |
| 4 | **Drawdown curve subplot** | Third subplot below volume. Computed from close prices already available. |
| 5 | **Integrity check badge** | Call `load_run_artifacts` + `evaluate_run` on the selected run and show pass/fail next to the run selector. Reuses existing ewm-core evaluator. |

### P2 — High impact, moderate effort

| # | Feature | Notes |
|---|---------|-------|
| 6 | **Colour-coded trajectory rows** | Use `st.dataframe` with `column_config` styling — green rows for buys, red for sells. Requires pandas Styler or Streamlit column config. |
| 7 | **Persistent sidebar state** | Wrap all sidebar widgets with `st.session_state` keys so parameter values survive page reruns without resetting. |
| 8 | **Dark mode toggle** | Sidebar checkbox switches Plotly template between `plotly_white` and `plotly_dark` and persists in session state. |
| 9 | **Run manifest summary panel** | Parse `manifest.json` from selected run and display mode, symbols, budgets, strategy path in an `st.expander`. |
| 10 | **Side-by-side run diff** | Second run selector in sidebar; show two manifests in `st.columns(2)` with differing fields highlighted. |

### P3 — Moderate impact, higher effort

| # | Feature | Notes |
|---|---------|-------|
| 11 | **Multi-ticker comparison** | Overlay two GBM paths normalised to 100 on the same chart. Requires second set of sidebar controls or a ticker list input. |
| 12 | **Date range picker for live data** | Replace period selectbox with `st.date_input(range)` and pass `start`/`end` to `yf.download`. |
| 13 | **Preset GBM profiles** | Sidebar quick-select: Low vol / Trending / Mean-reverting. Each sets drift + volatility to preset values via session state. |
| 14 | **Multi-page layout** | Migrate to `st.navigation` with pages: Chart · Trajectory · Artifacts · Experiment. Reduces per-page clutter significantly. |
| 15 | **Experiment-level view** | Load all runs under a root, compute aggregate metrics (avg steps, integrity pass rate, avg return) in a summary table. Reuses `experiment_evaluator.py`. |

---

## Deferred (nice-to-have, low priority)

- `st.toast` fetch notifications
- Bollinger Bands overlay
- Watchdog install prompt for hot-reload performance
