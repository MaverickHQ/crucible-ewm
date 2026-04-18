# Learning Layer (v0.8.5)

> **Note**: v0.8.5 adds the Policy Feedback layer that completes the learning loop.

The learning layer in v0.8.4 provides a minimal scaffold for consuming validated trajectory data as learning-ready datasets.

This is NOT reinforcement learning training. It is a deterministic scaffold that demonstrates how the architecture can close the loop from experiments to learning inputs.

## Architecture

The learning layer sits at the top of the experimental architecture:

```
environment → trajectories → artifacts → evaluation → experiments → dataset → learner
```

## Components

### Selector

The selector filters runs from an experiment based on structural validity:

- `manifest_valid=True` - Run has valid manifest
- `integrity_errors=[]` - No artifact integrity issues
- Optionally include/exclude truncated runs

```python
from services.core.learning import select_learning_runs

runs = select_learning_runs(
    experiment_dir,
    require_valid=True,
    include_truncated=True,
)
```

### Dataset Export

Trajectories are exported as JSONL (JSON Lines) format, one record per trajectory step:

```python
from services.core.learning import export_learning_dataset

output_path = export_learning_dataset(
    experiment_dir,
    output_file,
    require_valid=True,
)
```

### JSONL Dataset Format

Each line in the exported dataset is a JSON object:

```json
{"run_id": "run-001", "step_index": 0, "observation": {"step": 0, "prices": {"AAPL": 100.0}}, "action": {"type": "hold"}, "done": false}
{"run_id": "run-001", "step_index": 1, "observation": {"step": 1, "prices": {"AAPL": 101.0}}, "action": {"type": "buy", "symbol": "AAPL"}, "done": false}
```

Fields:

- `run_id`: Unique run identifier
- `step_index`: Position in trajectory
- `observation`: Environment observation at step
- `action`: Agent action taken
- `done`: Whether this is terminal step

### Replay Iterator

The replay module provides an iterator over exported datasets:

```python
from services.core.learning import iter_trajectory_steps

for step in iter_trajectory_steps(dataset_path):
    print(step["run_id"], step["action"])
```

### Stub Learner

The stub learner computes aggregate statistics from trajectory datasets:

```python
from services.core.learning import run_stub_learner

run_stub_learner(dataset_path, report_path)
```

The stub learner computes:

- Total runs and steps
- Average steps per run
- Action type counts (hold, buy, sell)
- Symbol counts

This is intentionally minimal. It demonstrates the interface without implementing actual RL training.

## Usage

Run the demo:

```bash
python3 scripts/demo_learning_loop.py
```

Example output:

```
STEP 1: Select Learning Runs
Selected 2 runs

STEP 2: Export Learning Dataset
Rows exported: 8

STEP 3: Run Stub Learner
Total runs: 2
Total steps: 8
```

## Design Principles

1. **Deterministic**: All outputs are reproducible
2. **Minimal**: Only essential scaffolding, no actual training
3. **Trading-aligned**: Fields match trading environment (actions: hold/buy/sell, symbols)
4. **Essay 10 aligned**: Only trusted experimental evidence enters the learning loop

## Evidence Policy (v0.8.5 - NEW)

v0.8.5 adds the **Policy Feedback** layer that completes the learning loop. The learner stub's output can now be converted into an evidence policy that influences future trading decisions.

### What It Is

- A deterministic policy builder from learning reports
- A decision helper that applies evidence-based preferences
- The final link: experiments → evidence → policy → decisions

### What It Is NOT

- RL training with reward optimization
- Policy gradient learning
- Model weight training

### Components

#### Evidence Policy Structure

```json
{
  "environment_type": "trading",
  "generated_from": "outputs/learning/demo_learning_report.json",
  "evidence_runs": 2,
  "default_action": "hold",
  "action_preferences_by_symbol": {
    "AAPL": "hold",
    "MSFT": "hold"
  },
  "action_preferences_by_step": {
    "0": "hold",
    "1": "buy"
  }
}
```

#### Policy Builder

```python
from services.core.policy import build_evidence_policy_from_learning_report

build_evidence_policy_from_learning_report(
    report_path=report_path,
    output_path=policy_path,
)
```

#### Policy Applicator

```python
from services.core.policy import apply_evidence_policy

decision = apply_evidence_policy(observation, policy)
# Returns: {"action": "hold", "source": "symbol", "policy_used": True}
```

### Decision Logic

The policy applicator uses simple deterministic rules:

1. If symbol has a known preference, use that action
2. Else if step position has a known preference, use that action
3. Else fall back to default_action (typically "hold")

### Usage

Run the complete policy feedback demo:

```bash
# Export learning dataset
python3 scripts/export_learning_dataset.py

# Run learner stub
python3 scripts/run_learning_stub.py

# Build evidence policy
python3 scripts/build_evidence_policy.py \
  --learning-report outputs/learning/demo_learning_report.json \
  --output outputs/learning/evidence_policy.json

# Run policy feedback demo
python3 scripts/demo_policy_feedback_loop.py
```

## Future Work

The current learner is a scaffold. Future iterations may explore:

- World model learning from trajectories
- Policy optimization
- Experiment-driven agent improvement
