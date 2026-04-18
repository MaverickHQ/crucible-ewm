import os

import pytest

from services.core.planner import BedrockPlanner
from services.core.policy.versioning import ensure_policy_metadata
from services.core.state import RiskLimits, State

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BEDROCK_TESTS") != "1",
    reason="Bedrock tests are disabled by default.",
)


def test_bedrock_planner_integration():
    if os.getenv("ENABLE_BEDROCK_PLANNER") != "1":
        pytest.skip("ENABLE_BEDROCK_PLANNER is not enabled.")
    if not os.getenv("AWS_REGION") or not os.getenv("BEDROCK_MODEL_ID"):
        pytest.skip("Missing AWS_REGION or BEDROCK_MODEL_ID.")

    policy = ensure_policy_metadata({"policy_id": "default"})
    state = State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    planner = BedrockPlanner(
        model_id=os.environ["BEDROCK_MODEL_ID"],
        region_name=os.environ["AWS_REGION"],
    )
    result = planner.propose(state.to_dict(), policy, "approve")

    assert result.plan
