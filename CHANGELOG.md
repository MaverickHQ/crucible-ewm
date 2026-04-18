## v0.8.5 — Evidence Policy Feedback Loop
- **Deterministic learning-loop scaffold completed**: The architecture now closes the loop from experiments to decisions
- **Evidence policy added**: New `services.core.policy` module with evidence-based decision support
- **Policy builder**: Converts learning reports into deterministic evidence policies
- **Policy applicator**: Applies evidence-based preferences to trading decisions
- **Commands**: 
  - `python3 scripts/build_evidence_policy.py` - Build policy from learning report
  - `python3 scripts/demo_policy_feedback_loop.py` - Demonstrate policy-guided decisions
- **Tests**: New unit tests for evidence_policy and policy_feedback_loop
- **This is NOT RL training**: Deterministic policy-feedback scaffold, no model weights, no gradient descent
- All tests pass (lint + pytest)

## v0.8.4 — Learning Loop Scaffold
- **Learning dataset export**: Validated trajectories exported as JSONL for learning
- **Stub learner**: Computes aggregate statistics from trajectory datasets
- **Demo**: `python3 scripts/demo_learning_loop.py` demonstrates the learning loop
- **Tests**: Unit tests for selector, dataset_export, replay, stub_learner
- All tests pass

## v0.8.3
- R21: run-level structural evaluation from artifacts (deterministic JSON, integrity error codes)
- R22: experiment-level structural evaluation (aggregate JSON + per-run CSV)
- CLI: `ewm run evaluate ...` and `ewm experiment evaluate ...`
- Tests: unit suite clean (231 passed)

## v0.8.2.3

- CLI lazy import for experiment command (optional deps no longer required for non-experiment commands)
- Removed eager certifi import from experiment module
- Subprocess CLI tests now use sys.executable
- AWS integration tests resolve artifacts bucket via CloudFormation
- Test suite baseline: 0 failures (224 passed, 5 skipped)

## v0.8.2.2 — Runtime budgets enforcement + AWS integration tests
- **Runtime budgets enforcement**: `runtime_budgets.max_steps` is now enforced during loop execution
- **Handler supports runtime_budgets**: Handler accepts canonical `runtime_budgets` input (legacy `budgets` still supported)
- **DynamoDB correlation_id canonical**: Run records store `correlation_id` as canonical field, `trace_id` retained for backward compatibility
- **AWS integration tests**: No longer requires ARTIFACT_BUCKET env var - resolves bucket via CloudFormation outputs

## v0.8.2.1 — AWS validation + deployment verification
- **DynamoDB correlation_id**: Run records now store `correlation_id` (canonical field matching API/logs/EMF). `trace_id` retained for backward compatibility and will be deprecated in a future release.
## v0.8.2 — Manifest v2: runtime_budgets vs policy_limits
- **Manifest v2 schema**: Standardized "budgets" to mean runtime loop budgets (max_steps, max_tool_calls, etc.)
- **Separated trading/risk constraints**: Moved max_leverage, max_position_pct, max_position_value to policy_limits
- **Backward compatibility**: Deprecated "budgets" field included as alias for runtime_budgets (one release)
- **Request parsing**: Configs accept both legacy "budgets" and new "runtime_budgets"/"policy_limits" fields
- **Deprecation warnings**: Legacy budgets with trading keys emit warning to stderr
- **Error handling**: Mixed keys in legacy budgets returns structured error explaining the split

## v0.8.1-fixes — S3 Artifacts + Correlation ID (P02)
- **S3 Artifacts**: Loop now uploads trajectory/decision/deltas to S3
- **Float Rounding**: API cash_balance shows 2 decimal places
- **Correlation ID**: Full propagation (header → X-Ray → UUID)
- All 117 unit tests pass

## v0.8.0 — Health, Contract Tests, Config Strategy (R3-R7, R10)
- **R6**: Added `/health` endpoint with deterministic payload per OpenSpec
- **R4**: Standardized API error format (code, message, details, request_id)
- **R10**: Added contract tests in `tests/contract/`
- **R7**: Loop strategy path is now configurable via `strategy_path` field
- **R3**: Extracted shared artifact serialization (`serialize_simulation_result`)
- **R5**: Added structured logging module with correlation ID support
- All 117 unit tests pass

## v0.7.10-cli — CLI runs inspection (P01)
- Enhanced 'ewm runs latest' with robust parsing for dict-of-runs format
- Added decision field (APPROVED/REJECTED/UNKNOWN)
- Human-readable rejection errors with code and message
- Rounded money values (2 decimal places)
- created_at timestamp display in summary
- Improved 'plan: none' wording
- 11 unit tests for CLI runs commands
- All tests pass (lint + pytest)

# Changelog

## v0.7.2 — AgentCore Memory (Cost-safe)
- Added AgentCore memory handler with explicit budgets for ops/bytes.
- Memory artifacts include decision/report/budgets/memory traces.
- New smoke/demo scripts and Make targets for memory path.

## v0.7.0 — AgentCore Hello (Cost-safe)
- Added AgentCore hello handler + gateway endpoint (no model calls, no memory).
- Minimal artifacts written to S3 (decision.json + report.md).
- New Make targets and smoke/demo script for hello path.

## v0.6.0 — Local Paper Broker + Execution Events
- Local broker abstraction with deterministic execution events.
- Executions artifacts now include broker events alongside per-trade ledger rows.
- Demo + replay scripts print execution events before the ledger.

## v0.5.0 — Local Execution Loop + Ledger
- Local loop demo that runs strategy → simulate → verify → execute.
- Execution ledger persisted alongside tape/report artifacts.
- Replay script for executions with deterministic table output.

## v0.4.0 — Trade Tape + Report
- Trade tape demo loop with tape.json/csv + report.md artifacts
- Strategy signal rationales emitted for thresholds/SMA/z-score rules
- New observability helpers for tape/report rendering

## v2.2.0 — AWS Planner Execution
- AWS simulate handler supports planner mode for mock/optional Bedrock.
- New AWS planner demo and smoke scripts + Makefile targets.
- Planner metadata persisted and validated in AWS integration tests.
- CDK wiring for gated Bedrock invoke permissions.

## v2.0.0 — Provider-neutral Planner
- Planner interface with deterministic mock planner
- Planner proposals always verified by the world model
- Planner metadata persisted alongside runs and artifacts

## v1.1.1 — Explainability, State Deltas, Policy Versioning
- Deterministic explanation strings for accepted and rejected steps
- Deltas artifact for step-by-step state changes
- Policy hash/version embedded in decisions and run metadata

## v1.1.0 — Executable World Model on AWS
- Deployed Minimum Viable World Model using AWS Lambda, DynamoDB, and S3
- Idempotent simulation and execution handlers
- Cloud artifacts for trajectories and decisions
- Smoke tests and end-to-end AWS demos

## v1.0.0 — Minimum Viable World Model (Local)
- Explicit state, actions, transitions, and verification
- Deterministic market paths and plan simulation
- Local persistence and artifact generation
- End-to-end demo with approval/rejection flows