# Experiments

Experiments are the aggregation layer for trajectory data. They collect runs, validate structural correctness, and produce learning-ready datasets.

## Directory Structure

An experiment directory contains:

```
experiment/
├── evaluation_summary.json    # Aggregated run results
├── artifacts/                # Per-run trajectory data
│   ├── run-001/
│   │   ├── manifest.json
│   │   ├── trajectory.json
│   │   ├── decision.json
│   │   └── deltas.json
│   └── run-002/
│       └── ...
└── datasets/                 # Exported learning datasets (optional)
    └── trajectories.jsonl
```

## Evaluation Summary

The `evaluation_summary.json` contains aggregated results from all runs:

```json
{
  "aggregate": {
    "total_runs": 10,
    "runs_with_integrity_errors": 1,
    "runs_without_integrity_errors": 9,
    "pct_integrity_fail": 10.0,
    "avg_steps_executed": 5.2
  },
  "runs": [
    {
      "run_id": "run-001",
      "manifest_valid": true,
      "integrity_errors": [],
      "steps_executed": 7,
      "truncated_by_budget": false
    }
  ],
  "summary": {
    "total_runs": 10,
    "ok_runs": 9,
    "failed_runs": 1
  }
}
```

## Artifacts

Each run directory contains:

- **manifest.json**: Run metadata (mode, symbols, runtime version)
- **trajectory.json**: Sequence of observations and actions
- **decision.json**: Decision context
- **deltas.json**: State transitions

## Flow: Run → Evaluation → Experiment → Dataset

```
1. Run executes → produces artifacts/
2. Evaluation checks → produces evaluation_summary.json
3. Aggregation collects → creates experiment/
4. Learning exports → produces dataset (JSONL)
```

## Usage

Experiments are created by the evaluation system. To work with experiments:

```python
from services.core.learning import select_learning_runs, export_learning_dataset

# Select valid runs
runs = select_learning_runs(experiment_dir, require_valid=True)

# Export to learning dataset
export_learning_dataset(experiment_dir, output_path)
```

## Use Cases

- Compare strategy performance across runs
- Identify structurally valid trajectories for learning
- Aggregate metrics across experiments
- Generate learning datasets from validated runs

## From Experiments to Decisions (v0.8.5)

v0.8.5 completes the loop from experiments to decisions through the Policy Feedback layer.

### The Complete Loop

```
Run → Artifacts → Evaluation → Experiment → Evidence Dataset 
                                            ↓
                              Learning Report ← Learner Stub
                                            ↓
                                    Evidence Policy
                                            ↓
                               Future Decisions ← Policy Applied
```

### How It Works

1. **Run Experiments**: Execute agent experiments with market environments
2. **Collect Evidence**: Validated trajectories become the evidence dataset
3. **Analyze Evidence**: Learner stub produces learning report with heuristics
4. **Build Policy**: Evidence policy captures action preferences by symbol/step
5. **Apply Policy**: When making new decisions, consult evidence policy

### Example Commands

```bash
# Export learning dataset from experiments
python3 scripts/export_learning_dataset.py

# Run learner stub to analyze evidence
python3 scripts/run_learning_stub.py

# Build evidence policy from report
python3 scripts/build_evidence_policy.py \
  --learning-report outputs/learning/demo_learning_report.json \
  --output outputs/learning/evidence_policy.json

# Run demo showing evidence-informed decisions
python3 scripts/demo_policy_feedback_loop.py
```

### What This Enables

- **Deterministic feedback**: Same evidence always produces same policy
- **Transparent decisions**: Easy to trace why a decision was made
- **No RL required**: Simple heuristic-based policy from experiment evidence
- **Essay 10 aligned**: The learning loop is now architecturally complete
