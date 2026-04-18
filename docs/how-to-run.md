# How to Run Executable World Models

This guide explains how to run the complete learning loop locally and on AWS.

---

## What the Project Does

Executable World Models (EWM) is a research framework for building deterministic experimental systems around intelligent agents.

The project demonstrates:

- **Deterministic experiments**: Reproducible agent behavior with explicit trajectory recording
- **Trajectories**: Sequence of observations, decisions, and state transitions
- **Evidence**: Validated trajectory data that can be analyzed for patterns
- **Policy feedback**: Evidence-based policies that influence future decisions

The complete learning loop:

```
environment → trajectories → artifacts → evaluation → experiments 
    → evidence dataset → learning report → evidence policy 
    → policy-guided decisions
```

This is NOT reinforcement learning:

- No model weights are learned
- No gradient descent occurs
- No exploration/exploitation tradeoff
- Simply: past experiment evidence influences future decisions

---

## Local Quickstart

### Setup

Install dependencies:

```bash
make setup
```

Run linting and tests:

```bash
make lint
pytest -q tests/unit --ignore=infra
```

### Run the Demos

#### Demo 1: Learning Loop

Demonstrates the basic learning scaffold:

```bash
python3 scripts/demo_learning_loop.py
```

What it shows:

- Selecting valid runs from experiments
- Exporting trajectory data to JSONL
- Running the learner stub to compute statistics

#### Demo 2: Policy Feedback Loop

Demonstrates evidence policy creation and application:

```bash
python3 scripts/demo_policy_feedback_loop.py
```

What it shows:

- Building evidence policy from learning report
- Applying policy to observations
- Comparing baseline vs policy-informed decisions

#### Demo 3: Policy-Guided Trading Agent

Demonstrates a policy-guided agent making decisions in the trading environment:

```bash
python3 scripts/demo_policy_guided_trading_agent.py
```

What it shows:

- Loading evidence policy
- Creating a PolicyGuidedAgent
- Running agent through trading environment steps
- Policy consulted at each step for decision-making

#### Demo 4: End-to-End Learning Loop

Demonstrates the complete loop from environment to policy-guided decisions:

```bash
python3 scripts/demo_end_to_end_learning_loop.py
```

What it proves:

- Experiment runs selected
- Dataset exported (non-zero rows)
- Learning report generated
- Evidence policy built (non-empty)
- Policy-guided decisions made

---

## What Each Demo Proves

| Demo | Purpose |
|------|---------|
| `demo_learning_loop.py` | Basic learning scaffold: runs → dataset → report |
| `demo_policy_feedback_loop.py` | Policy creation and application to observations |
| `demo_policy_guided_trading_agent.py` | Agent uses policy in trading environment |
| `demo_end_to_end_learning_loop.py` | Complete loop: experiments → evidence → policy → decisions |

---

## Expected Outputs

### Dataset Export

```
Dataset exported to: outputs/learning/demo_trajectories.jsonl
Rows exported: 8
```

### Evidence Policy

```json
{
  "environment_type": "trading",
  "evidence_runs": 2,
  "default_action": "hold",
  "action_preferences_by_symbol": {
    "AAPL": "hold",
    "MSFT": "hold"
  },
  "action_preferences_by_step": {
    "0": "hold"
  }
}
```

### Policy-Guided Decisions

```
Step 0: Decision for AAPL at step 0: hold (policy preference for symbol)
Step 1: Decision for AAPL at step 1: hold (policy preference for step position 1)
```

---

## AWS Path

### Deploy

```bash
make deploy-agentcore-loop
```

### Resolve API URL

```bash
export AWS_PROFILE=beyond-tokens-dev
export AWS_REGION=us-east-1

export AGENTCORE_LOOP_API_URL=$(aws cloudformation describe-stacks \
  --stack-name BeyondTokensStack \
  --region $AWS_REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentCoreLoopApiUrl`].OutputValue' \
  --output text)
```

### Health Check

```bash
curl -sS "$AGENTCORE_LOOP_API_URL/health" | python3 -m json.tool
```

### Run Integration Tests

```bash
pytest -q tests/integration/test_api_contract_errors.py
pytest -q tests/integration/test_budget_enforcement.py
pytest -q tests/integration/test_artifact_integrity.py
pytest -q tests/integration/test_dynamodb_run_records.py
python3 scripts/verify_observability_v0_8_2_1.py
```

### Note

The demos are primarily designed to run locally. AWS deployment validates runtime compatibility and integration with cloud services.

---

## Troubleshooting

### Missing AWS Credentials

If you see errors about AWS credentials:

```bash
export AWS_PROFILE=beyond-tokens-dev
export AWS_REGION=us-east-1
```

Or configure your credentials:

```bash
aws configure
```

### Missing Fixture Artifacts

If you see "Learning fixture not found":

```bash
# The fixture should be at:
ls tests/fixtures/learning_experiment/
```

### Policy Fallback Behavior

If no evidence exists for a symbol or step:

- Default action is "hold"
- Policy decision source shows "default"
- policy_used is False

This is expected behavior—the agent falls back to safe defaults when no evidence exists.

### Dataset Export Returns Zero Rows

Check that:

1. The experiment fixture exists: `tests/fixtures/learning_experiment/`
2. Evaluation summary is present: `evaluation_summary.json`
3. Run artifacts have valid structure

---

## Next Steps

After running the demos, you can:

1. **Examine the outputs**: Check `outputs/learning/` for generated artifacts
2. **Modify the fixture**: Add more runs to `tests/fixtures/learning_experiment/`
3. **Build your own policy**: Point to your experiment directory
4. **Read the docs**: See `docs/architecture.md` and `docs/learning.md` for deeper details

---

## Summary

The learning loop is now complete:

1. **Experiments** produce validated trajectories
2. **Learning** exports datasets and runs the learner stub
3. **Policy** captures action preferences from evidence
4. **Agent** consults policy to make informed decisions

This proves the architecture can close the loop from experiments to future decisions—without RL training.
