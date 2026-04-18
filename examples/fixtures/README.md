# Fixtures

This folder holds deterministic fixtures used by local demos and tests.

## Market path fixture

`trading_path.json` is a deterministic, ticker-aligned market path used for local planning demos.
It is accurate-ish, not precise, and intentionally avoids any external data sources.

Regenerate it deterministically:

```bash
python3 scripts/generate_price_path.py \
  --tickers AAPL,MSFT \
  --steps 5 \
  --seed 42 \
  --out examples/fixtures/trading_path.json
```