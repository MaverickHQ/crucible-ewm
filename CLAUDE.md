# ewm-core

Observable trajectory infrastructure. Trading domain reference implementation.
Part of the Crucible project.
GitHub: github.com/MaverickHQ/crucible-ewm

## Active phase: Phase 1 (weeks 1–2)
1. Refactor services/core/ into installable ewm-core package
2. Synthetic market data generator (GBM model, OHLCV output)
3. Streamlit dashboard (candlestick chart, trajectory table, artifact viewer)
4. yfinance integration — live data toggle
5. PyPI release as ewm-core
6. Deploy to Streamlit Cloud

## Commands
make setup          install dependencies
make lint           run linter  
pytest              run all tests
python3 scripts/demo_learning_loop.py   main demo

## Structure
services/core/environment/  world environments
services/core/eval/         structural evaluation
services/core/learning/     learning scaffold
scripts/                    demos and tools
outputs/learning/           generated — do not edit

## Conventions
Python 3.11+ · type hints throughout · no global state
Artifacts: JSON, deterministic given same seed
Tests in tests/ · pytest

## Do not load
outputs/ · .venv/ · __pycache__/ (enforced via .claudeignore)

## Next repo
player-coach/ — adversarial quality loop
