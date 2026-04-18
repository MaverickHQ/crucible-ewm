from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3

from services.aws.utils.output_loader import load_outputs

BASE_DIR = ROOT
OUTPUTS_PATH = Path(os.environ.get("AWS_OUTPUTS_PATH", BASE_DIR / "infra" / "cdk" / "cdk-outputs.json"))


def main() -> None:
    outputs = load_outputs(OUTPUTS_PATH)
    simulate_fn = outputs["SimulateFunctionName"]

    client = boto3.client("lambda")
    payload = {
        "plan": [{"type": "PlaceBuy", "symbol": "AAPL", "quantity": 1}],
    }

    response = client.invoke(
        FunctionName=simulate_fn,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = json.loads(response["Payload"].read().decode("utf-8"))
    print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()
