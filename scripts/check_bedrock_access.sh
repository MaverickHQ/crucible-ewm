#!/usr/bin/env bash
set -euo pipefail

PROFILE="${AWS_PROFILE:-beyond-tokens-dev}"
REGION="${AWS_REGION:-us-east-1}"

echo "Checking AWS CLI access for profile: $PROFILE"
aws sts get-caller-identity --profile "$PROFILE" >/tmp/bedrock_sts.json

echo "Listing Bedrock models in $REGION (default us-east-1)"
aws bedrock list-foundation-models --profile "$PROFILE" --region "$REGION" >/tmp/bedrock_models.json

MODEL_ID=$(python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/bedrock_models.json').read_text())
models = [m.get('modelId') for m in payload.get('modelSummaries', []) if m.get('modelId')]
preferred = "anthropic.claude-3-haiku-20240307-v1:0"
if preferred in models:
    print(preferred)
elif models:
    print(models[0])
else:
    print("")
PY
)

if [[ -z "$MODEL_ID" ]]; then
  echo "No model IDs found. Check Bedrock access in the console." >&2
  exit 1
fi

cat > /tmp/bedrock_req.json <<'EOF'
{
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 256,
  "messages": [
    {"role": "user", "content": "Say hello in one short sentence."}
  ]
}
EOF

echo "Invoking model: $MODEL_ID"
aws bedrock-runtime invoke-model \
  --profile "$PROFILE" \
  --region "$REGION" \
  --model-id "$MODEL_ID" \
  --body fileb:///tmp/bedrock_req.json \
  /tmp/bedrock_resp.json >/tmp/bedrock_invoke.out

echo "OK: Bedrock invoke succeeded"
echo "Suggested exports:"
echo "export AWS_PROFILE=$PROFILE"
echo "export AWS_REGION=$REGION"
echo "export BEDROCK_MODEL_ID=$MODEL_ID"
echo "export ENABLE_BEDROCK_PLANNER=1"