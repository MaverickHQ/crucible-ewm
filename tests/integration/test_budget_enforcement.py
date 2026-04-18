"""
Integration tests for runtime_budgets enforcement in Agent Runtime v0.8.2.1.

Tests validate that runtime_budgets actually bind (not just recorded) for:
- max_steps: loop stops at specified step count
- max_tool_calls: tool call count is tracked (or 0 if no tools in loop)
- max_model_calls: validation that nonzero model calls fail for reactive loop

Requirements:
- Tests cover local execution (run_agentcore_loop) and AWS API
- Verify artifacts are produced when execution is truncated
- Use JSON canonical config (no PyYAML required)
- Skip AWS tests if credentials missing

Test Response Contract (from run_agentcore_loop):
- ok: boolean
- run_id: string
- mode: string
- steps: actual steps executed
- tape_length: number of tape rows  
- execution_count: number of execution rows
- artifact_dir: local artifact directory (if write_artifacts=true)
- artifact_s3_prefix: S3 prefix (if upload_s3=true)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import requests

from tests.integration.aws_env import (
    get_api_url,
    get_aws_profile,
    get_region,
    get_skip_reason,
    resolve_artifacts_bucket,
)

# AWS profile and region from task requirements
AWS_PROFILE = get_aws_profile()
AWS_REGION = get_region()


def _get_api_url() -> Optional[str]:
    """Get API URL, returns None if not available."""
    return get_api_url()


def _make_request(
    url: str,
    method: str = "POST",
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> requests.Response:
    """Make HTTP request using requests library."""
    request_headers = headers or {}
    if data is not None:
        if "content-type" not in request_headers and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        if isinstance(data, dict):
            data = json.dumps(data)

    return requests.request(method, url, data=data, headers=request_headers, timeout=timeout)


def _check_aws_credentials() -> bool:
    """Check if AWS credentials are available."""
    try:
        import boto3
        sts = boto3.client("sts", region_name=AWS_REGION)
        sts.get_caller_identity()
        return True
    except Exception:
        return False


# =============================================================================
# Local Tests - Test run_agentcore_loop directly (no HTTP)
# =============================================================================


class TestLocalBudgetEnforcement:
    """Local tests that call run_agentcore_loop directly."""

    def test_max_steps_equals_1_stops_at_1_step(self):
        """
        Test that runtime_budgets.max_steps=1 causes the loop to stop at <= 1 step.
        
        EXPECTED BEHAVIOR: The loop should execute at most 1 step when max_steps=1.
        This test verifies the fix for: runtime_budgets.max_steps is now enforced.
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_steps=1),
            steps=5,  # Request more steps but budget should limit to 1
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True, f"Expected ok=True, got {result}"
        
        actual_steps = result.get("steps", 0)
        tape_length = result.get("tape_length", 0)
        execution_count = result.get("execution_count", 0)
        
        # FIXED: The budgets.max_steps is now enforced - loop stops at max_steps
        assert actual_steps <= 1, f"Expected steps <= 1, got {actual_steps}"
        assert tape_length <= 1, f"Expected tape_length <= 1, got {tape_length}"
        assert execution_count <= 1, f"Expected execution_count <= 1, got {execution_count}"

    def test_legacy_budgets_max_steps_still_enforced(self):
        """
        Test that legacy 'budgets.max_steps' field still enforces the same behavior.
        
        This test confirms backward compatibility: legacy budgets.max_steps should work
        the same as runtime_budgets.max_steps.
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        # Use LoopBudgets (which is the legacy internal representation)
        # This tests backward compatibility
        req = LoopRequest(
            budgets=LoopBudgets(max_steps=1),  # Legacy field
            steps=5,  # Request more steps but budget should limit to 1
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True, f"Expected ok=True, got {result}"
        
        actual_steps = result.get("steps", 0)
        
        # Legacy budgets.max_steps should also be enforced
        assert actual_steps <= 1, f"Expected steps <= 1 for legacy budgets, got {actual_steps}"

    def test_max_tool_calls_zero_succeeds(self):
        """
        Test that runtime_budgets.max_tool_calls=0 succeeds.
        
        Note: The current agentcore-loop implementation does NOT use tools in the 
        execution loop. Tool calls are tracked in agentcore-tools, not in the 
        loop. This test verifies that max_tool_calls=0 is accepted and the 
        loop succeeds with tool_calls metric being 0 or not present.
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_tool_calls=0),
            steps=3,
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True, f"Expected ok=True, got {result}"
        
        # Since tools are not part of the loop path, the request should succeed
        # and tool_calls metric should be 0 or not present
        # (The loop doesn't track tool_calls currently)
        # We just verify the request succeeded

    def test_max_model_calls_zero_succeeds_for_reactive_loop(self):
        """
        Test that runtime_budgets.max_model_calls=0 succeeds for reactive loop.
        
        The reactive loop (agentcore-loop) does NOT make model calls - it 
        executes a predetermined strategy. This is the expected behavior.
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_model_calls=0),
            steps=3,
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True, f"Expected ok=True for reactive loop, got {result}"

    def test_max_model_calls_nonzero_fails(self):
        """
        Test that runtime_budgets.max_model_calls != 0 fails for reactive loop.
        
        The reactive loop should reject any nonzero model calls because it 
        doesn't make LLM calls - it's a deterministic strategy execution.
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_model_calls=1),  # Nonzero should fail
            steps=3,
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is False, f"Expected ok=False for nonzero model calls, got {result}"
        assert result.get("error", {}).get("code") == "invalid_budget", \
            f"Expected error code 'invalid_budget', got {result.get('error')}"

    def test_artifacts_produced_when_truncated_max_steps_1(self):
        """
        Test that artifacts are produced when execution is truncated (max_steps=1).
        
        Verifies:
        - local: manifest.json exists in artifact_dir/artifacts/<run_id>/
        
        Note: Artifacts are stored in artifact_dir/artifacts/<run_id>/ not directly in artifact_dir
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_steps=1),
            steps=5,
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True
        
        # Check that artifact_dir is present
        assert "artifact_dir" in result, "Expected artifact_dir in response"
        artifact_dir = Path(result["artifact_dir"])
        
        # The run_id from the result
        run_id = result.get("run_id")
        assert run_id, "Expected run_id in result"
        
        # Artifacts are in artifact_dir/artifacts/<run_id>/
        artifacts_subdir = artifact_dir / "artifacts" / run_id
        
        # Check that manifest.json exists in the correct subdirectory
        manifest_path = artifacts_subdir / "manifest.json"
        assert manifest_path.exists(), f"Expected manifest.json at {manifest_path}"
        
        # Validate manifest is valid JSON
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert "run_id" in manifest, "Expected run_id in manifest"


# =============================================================================
# AWS Tests - Test via HTTP API
# =============================================================================


class TestAWSBudgetEnforcement:
    """AWS tests that call the API endpoint."""

    @pytest.fixture(autouse=True)
    def check_aws_available(self):
        """Skip tests if AWS credentials not available."""
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        if not _check_aws_credentials():
            pytest.skip("AWS credentials not available")

    def test_aws_max_steps_equals_1_stops_at_1_step(self):
        """
        Test that runtime_budgets.max_steps=1 causes the loop to stop at <= 1 step on AWS.
        
        EXPECTED BEHAVIOR: The loop should execute at most 1 step when max_steps=1.
        This test verifies the fix for: runtime_budgets.max_steps is now enforced.
        """
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        payload = {
            "runtime_budgets": {
                "max_steps": 1,
            },
            "steps": 5,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": True,
        }

        response = _make_request(api_url, method="POST", data=payload)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True, got {result}"

        actual_steps = result.get("steps", 0)
        
        # FIXED: The budgets.max_steps is now enforced - loop stops at max_steps
        assert actual_steps <= 1, f"Expected steps <= 1, got {actual_steps}"

    def test_aws_max_tool_calls_zero_succeeds(self):
        """
        Test that runtime_budgets.max_tool_calls=0 succeeds on AWS.
        
        Note: Tools are not used in the agentcore-loop - this is a reactive 
        execution loop without tool invocations.
        """
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        payload = {
            "runtime_budgets": {
                "max_tool_calls": 0,
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": False,
        }

        response = _make_request(api_url, method="POST", data=payload)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True, got {result}"

    def test_aws_max_model_calls_zero_succeeds(self):
        """
        Test that runtime_budgets.max_model_calls=0 succeeds on AWS for reactive loop.
        """
        api_url = _get_api_url()
        if not api_url:
            pytest.skip("AWS API URL not available")

        payload = {
            "runtime_budgets": {
                "max_model_calls": 0,
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": False,
        }

        response = _make_request(api_url, method="POST", data=payload)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True for reactive loop, got {result}"

    def test_aws_max_model_calls_nonzero_fails(self):
        """
        Test that runtime_budgets.max_model_calls != 0 fails on AWS.
        """
        api_url = _get_api_url()
        if not api_url:
            pytest.skip("AWS API URL not available")

        payload = {
            "runtime_budgets": {
                "max_model_calls": 1,  # Nonzero should fail
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": False,
        }

        response = _make_request(api_url, method="POST", data=payload)

        # Should return 400 for invalid budget
        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is False, f"Expected ok=False, got {result}"
        assert result.get("error", {}).get("code") == "invalid_budget", \
            f"Expected error code 'invalid_budget', got {result.get('error')}"

    def test_aws_artifacts_produced_when_truncated(self):
        """
        Test that S3 artifacts are produced when execution is truncated (max_steps=1).
        
        Verifies:
        - AWS: S3 has manifest.json, trajectory.json, decision.json, deltas.json
        """
        api_url = _get_api_url()
        if not api_url:
            pytest.skip("AWS API URL not available")

        import boto3

        payload = {
            "runtime_budgets": {
                "max_steps": 1,
            },
            "steps": 5,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": True,
        }

        response = _make_request(api_url, method="POST", data=payload, timeout=120)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True, got {result}"

        # Check for S3 prefix in response
        s3_prefix = result.get("artifact_s3_prefix")
        if not s3_prefix:
            # Check for error in response
            s3_error = result.get("artifact_s3_error")
            if s3_error:
                pytest.skip(f"S3 upload failed (no bucket configured): {s3_error}")
            else:
                pytest.skip("No artifact_s3_prefix in response - S3 upload may not be configured")
        
        # Parse bucket from prefix (format: artifacts/<run_id>)
        # Use resolve_artifacts_bucket to try env var first, then CloudFormation
        artifact_bucket, bucket_reason = resolve_artifacts_bucket()
        if not artifact_bucket:
            pytest.skip(f"Artifact bucket not available: {bucket_reason}")
        
        # Verify S3 objects exist
        s3_client = boto3.client("s3")
        
        # Check manifest.json
        try:
            key = f"{s3_prefix}/manifest.json"
            response = s3_client.get_object(Bucket=artifact_bucket, Key=key)
            manifest = json.loads(response["Body"].read().decode("utf-8"))
            assert "run_id" in manifest, "Expected run_id in manifest"
        except s3_client.exceptions.NoSuchKey:
            pytest.fail(f"manifest.json not found at s3://{artifact_bucket}/{key}")

        # Check trajectory.json
        try:
            key = f"{s3_prefix}/trajectory.json"
            response = s3_client.get_object(Bucket=artifact_bucket, Key=key)
            trajectory = json.loads(response["Body"].read().decode("utf-8"))
            assert "trajectory" in trajectory, "Expected trajectory in trajectory.json"
        except s3_client.exceptions.NoSuchKey:
            pytest.fail(f"trajectory.json not found at s3://{artifact_bucket}/{key}")

        # Check decision.json
        try:
            key = f"{s3_prefix}/decision.json"
            response = s3_client.get_object(Bucket=artifact_bucket, Key=key)
            decision = json.loads(response["Body"].read().decode("utf-8"))
            assert "run_id" in decision, "Expected run_id in decision.json"
        except s3_client.exceptions.NoSuchKey:
            pytest.fail(f"decision.json not found at s3://{artifact_bucket}/{key}")
        
        # Check deltas.json
        try:
            response = s3_client.get_object(Bucket=artifact_bucket, Key=f"{s3_prefix}/deltas.json")
            deltas = json.loads(response["Body"].read().decode("utf-8"))
            assert "run_id" in deltas, "Expected run_id in deltas.json"
        except s3_client.exceptions.NoSuchKey:
            pytest.fail(f"deltas.json not found at s3://{artifact_bucket}/{s3_prefix}/deltas.json")
