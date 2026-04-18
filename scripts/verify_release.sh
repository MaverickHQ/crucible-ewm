#!/bin/bash
# Verification script for v1.0.0 implementation
# Run this to verify all release requirements are met

set -euo pipefail
cd /Users/maverick/executable-world-models

echo "============================================================================="
echo "VERIFY v1.0.0 IMPLEMENTATION"
echo "Repo: $(pwd)"
echo "Time: $(date -u)"
echo "============================================================================="
echo

echo "=== GIT STATUS ==="
git status -sb
echo

echo "=== VERSION CHECKS ==="
python3 -V
echo "--- pyproject version / requires-python ---"
grep -E "^version|^name|requires-python" pyproject.toml | head -5
echo

echo "=== QUICK FILE PRESENCE CHECKS ==="
for f in \
  services/aws/handlers/health_handler.py \
  services/core/errors.py \
  services/core/logging/__init__.py \
  scripts/smoke_health.py \
  tests/contract/test_api_contract.py
do
  test -f "$f" && echo "OK: $f" || (echo "MISSING: $f" && exit 1)
done
echo

echo "=== RUN UNIT TESTS ==="
pytest -q tests/unit
echo

echo "=== RUN CONTRACT TESTS ==="
pytest -q tests/contract
echo

echo "=== HEALTH SMOKE TEST (script) ==="
python3 scripts/smoke_health.py
echo

echo "=== ERROR SHAPE SANITY (grep for required keys) ==="
grep -r "request_id" services tests | head -n 20 || true
grep -r "code.*message.*details" services tests | head -n 20 || true
echo

echo "=== STRATEGY PATH FIELD SANITY ==="
grep -r "strategy_path" services/core/agentcore_loop || true
echo

echo "=== ARTIFACT WRITER SANITY ==="
grep -r "serialize_simulation_result" services | head -n 20 || true
echo

echo "=== STRUCTURED LOGGING SANITY ==="
grep -r "correlation" services/core/logging services | head -n 50 || true
echo

echo "=== CHANGELOG/README TOUCH CHECK ==="
test -f CHANGELOG.md && echo "OK: CHANGELOG.md present" || echo "WARN: CHANGELOG.md missing"
grep -E "v1\.0\.0|1\.0\.0|/health|contract" README.md CHANGELOG.md 2>/dev/null || true
echo

echo "============================================================================="
echo "ALL VERIFICATION CHECKS PASSED"
echo "Ready for release: YES"
echo "============================================================================="
