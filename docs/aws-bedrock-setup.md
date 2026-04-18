# Bedrock Access Setup (Local)

This guide helps validate local Bedrock access without committing any secrets.

## Prerequisites
- AWS CLI v2 installed (`aws --version`).
- An AWS profile with Bedrock permissions (example: `beyond-tokens-dev`).

## 1) Verify identity (sanitized)
```bash
AWS_PROFILE=beyond-tokens-dev aws sts get-caller-identity
```

If this fails, authenticate (SSO) or configure credentials:
```bash
aws sso login --profile beyond-tokens-dev
# or
aws configure --profile beyond-tokens-dev
```

## 2) List available models (us-east-1)
```bash
AWS_PROFILE=beyond-tokens-dev aws bedrock list-foundation-models --region us-east-1
```

Pick a model ID. Recommended default if available:
```
anthropic.claude-3-haiku-20240307-v1:0
```

## 3) Smoke test invoke (Anthropic)
Create a temporary request (do **not** save in repo):
```bash
cat > /tmp/bedrock_req.json <<'EOF'
{
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 256,
  "messages": [
    {"role": "user", "content": "Say hello in one short sentence."}
  ]
}
EOF
```

Invoke the model (response saved in `/tmp/bedrock_resp.json`):
```bash
AWS_PROFILE=beyond-tokens-dev aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-haiku-20240307-v1:0 \
  --body fileb:///tmp/bedrock_req.json \
  --region us-east-1 \
  /tmp/bedrock_resp.json
```

## 4) Run the Bedrock planner demo
```bash
export AWS_PROFILE=beyond-tokens-dev
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
export ENABLE_BEDROCK_PLANNER=1
make demo-local-bedrock
```

Expected: Scenario A rejects with fixture-priced actions and Scenario B approves with fixture prices. Explanations and artifact paths print in each scenario.

## Troubleshooting
- **AccessDenied**: ensure the caller has `bedrock:InvokeModel` permission.
- **ResourceNotFound/ValidationException**: confirm region `us-east-1` and model ID from the catalog.
- **Anthropic use-case gating**: enable the model in the Bedrock Console (Model Catalog).