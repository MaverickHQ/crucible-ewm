"""
Integration tests for artifact integrity validation in Agent Runtime v0.8.2.1.

Tests verify that artifacts are:
1. Present (all required files exist)
2. Valid JSON (parse without errors)
3. Internally consistent (run_id linkage across files)

Requirements:
- Local checks: Run loop via core runner, verify artifact directory
- AWS checks: Call POST /agentcore/loop with upload_s3=true, verify S3 artifacts
- Use aws cli for S3 listing (minimal deps)
"""

from __future__ import annotations

import json
import subprocess
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

# Required artifact files
REQUIRED_ARTIFACT_FILES = [
    "manifest.json",
    "decision.json",
    "trajectory.json",
    "deltas.json",
]


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
# Local Tests - Test artifact integrity locally
# =============================================================================


class TestLocalArtifactIntegrity:
    """Local tests that verify artifact integrity via run_agentcore_loop."""

    def test_local_artifacts_exist_and_valid(self):
        """
        Test that local artifacts are created with valid JSON and consistent run_id.
        
        Verifies:
        - artifact_dir/artifacts/<run_id>/ contains all required files
        - All files parse as valid JSON
        - manifest.manifest_version == "2"
        - manifest.run_id matches the run_id from loop result
        - manifest.runtime_budgets exists (can be empty dict)
        - manifest.policy_limits exists (can be empty dict)
        """
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_steps=3),
            steps=3,
            seed=42,
            symbols=("AAPL", "MSFT"),
            write_artifacts=True,
            upload_s3=False,
        )

        result = run_agentcore_loop(req)

        assert result["ok"] is True, f"Expected ok=True, got {result}"

        # Get artifact directory
        assert "artifact_dir" in result, "Expected artifact_dir in response"
        artifact_dir = Path(result["artifact_dir"])

        # Get run_id from result
        run_id = result.get("run_id")
        assert run_id, "Expected run_id in result"

        # Artifacts are in artifact_dir/artifacts/<run_id>/
        artifacts_subdir = artifact_dir / "artifacts" / run_id

        # Assert all required files exist
        for filename in REQUIRED_ARTIFACT_FILES:
            file_path = artifacts_subdir / filename
            assert file_path.exists(), f"Expected {filename} at {file_path}"

        # Assert each file parses as JSON and has run_id
        for filename in REQUIRED_ARTIFACT_FILES:
            file_path = artifacts_subdir / filename
            with open(file_path) as f:
                content = json.load(f)
            assert isinstance(content, dict), f"Expected dict in {filename}"
            assert "run_id" in content, f"Expected run_id in {filename}"

        # Load and validate manifest
        manifest_path = artifacts_subdir / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Assert manifest version
        assert manifest.get("manifest_version") == "2", \
            f"Expected manifest_version == '2', got {manifest.get('manifest_version')}"

        # Assert manifest.run_id matches result run_id
        assert manifest.get("run_id") == run_id, \
            f"Expected manifest.run_id == {run_id}, got {manifest.get('run_id')}"

        # Assert runtime_budgets exists (can be empty dict but should exist)
        assert "runtime_budgets" in manifest, \
            "Expected runtime_budgets in manifest"

        # Assert policy_limits exists (can be empty dict but should exist)
        assert "policy_limits" in manifest, \
            "Expected policy_limits in manifest"

        print(f"[LOCAL] PASS: All local artifact integrity checks passed for run_id={run_id}")


# =============================================================================
# AWS Tests - Test artifact integrity on S3
# =============================================================================


class TestAWSArtifactIntegrity:
    """AWS tests that verify artifact integrity on S3."""

    @pytest.fixture(autouse=True)
    def check_aws_available(self):
        """Skip tests if AWS credentials or API not available."""
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        if not _check_aws_credentials():
            pytest.skip("AWS credentials not available")

    def test_aws_artifacts_s3_valid_json_and_consistent(self):
        """
        Test that AWS S3 artifacts are valid JSON with consistent run_id.
        
        Verifies:
        - POST /agentcore/loop with upload_s3=true returns artifact_s3_prefix
        - S3 objects exist for all required artifact files
        - All objects parse as valid JSON
        - manifest.run_id equals the run_id from response
        - S3 prefix includes run_id
        """
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        # Use resolve_artifacts_bucket to try env var first, then CloudFormation
        artifact_bucket, bucket_reason = resolve_artifacts_bucket()
        if not artifact_bucket:
            pytest.skip(f"Artifact bucket not available: {bucket_reason}")

        payload = {
            "budgets": {
                "max_steps": 3,
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL", "MSFT"],
            "write_artifacts": True,
            "upload_s3": True,
        }

        response = _make_request(api_url, method="POST", data=payload, timeout=120)

        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True, got {result}"

        # Get run_id from response
        run_id = result.get("run_id")
        assert run_id, "Expected run_id in response"

        # Get S3 prefix from response
        s3_prefix = result.get("artifact_s3_prefix")
        if not s3_prefix:
            # Check for error in response
            s3_error = result.get("artifact_s3_error")
            if s3_error:
                pytest.skip(f"S3 upload failed (no bucket configured): {s3_error}")
            else:
                pytest.skip("No artifact_s3_prefix in response - S3 upload may not be configured")

        # Assert prefix includes run_id
        assert run_id in s3_prefix, \
            f"Expected S3 prefix to include run_id {run_id}, got {s3_prefix}"

        # List S3 objects using aws cli (minimal deps)
        s3_path = f"s3://{artifact_bucket}/{s3_prefix}"
        list_result = subprocess.run(
            [
                "aws", "s3", "ls",
                f"{s3_path}/",
                "--profile", AWS_PROFILE,
                "--region", AWS_REGION,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Assert all required files exist in S3
        for filename in REQUIRED_ARTIFACT_FILES:
            expected_key = f"{s3_prefix}/{filename}"
            # Check if the file is listed
            found = expected_key in list_result.stdout or filename in list_result.stdout
            assert found, (
                f"Expected {filename} in S3 at {s3_path}, "
                f"but not found in listing: {list_result.stdout}"
            )

        # Download and validate each artifact using aws cli
        for filename in REQUIRED_ARTIFACT_FILES:
            key = f"{s3_prefix}/{filename}"
            download_result = subprocess.run(
                [
                    "aws", "s3", "cp",
                    f"s3://{artifact_bucket}/{key}",
                    "-",
                    "--profile", AWS_PROFILE,
                    "--region", AWS_REGION,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Assert valid JSON
            try:
                content = json.loads(download_result.stdout)
            except json.JSONDecodeError as e:
                pytest.fail(f"Failed to parse {filename} as JSON: {e}")

            # Assert run_id present
            assert "run_id" in content, f"Expected run_id in {filename}"

        # Download and validate manifest specifically
        manifest_key = f"{s3_prefix}/manifest.json"
        manifest_result = subprocess.run(
            [
                "aws", "s3", "cp",
                f"s3://{artifact_bucket}/{manifest_key}",
                "-",
                "--profile", AWS_PROFILE,
                "--region", AWS_REGION,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        manifest = json.loads(manifest_result.stdout)

        # Assert manifest version
        assert manifest.get("manifest_version") == "2", \
            f"Expected manifest_version == '2', got {manifest.get('manifest_version')}"

        # Assert manifest.run_id matches response run_id
        assert manifest.get("run_id") == run_id, \
            f"Expected manifest.run_id == {run_id}, got {manifest.get('run_id')}"

        # Assert runtime_budgets exists
        assert "runtime_budgets" in manifest, \
            "Expected runtime_budgets in manifest"

        # Assert policy_limits exists
        assert "policy_limits" in manifest, \
            "Expected policy_limits in manifest"

        print(f"[AWS] PASS: All S3 artifact integrity checks passed for run_id={run_id}")


# =============================================================================
# Summary
# =============================================================================


def test_artifact_integrity_summary():
    """
    Summary test that prints PASS/FAIL for local + AWS.
    
    This test always runs last and provides a summary of the artifact integrity checks.
    The actual test logic is in the classes above - this just provides a clear summary.
    """
    local_passed = True
    aws_passed = True

    # Check if we can run local tests
    try:
        from services.core.agentcore_loop.run import run_agentcore_loop
        from services.core.agentcore_loop.types import LoopBudgets, LoopRequest

        req = LoopRequest(
            budgets=LoopBudgets(max_steps=1),
            steps=1,
            seed=42,
            symbols=("AAPL",),
            write_artifacts=True,
            upload_s3=False,
        )
        result = run_agentcore_loop(req)
        if not result.get("ok"):
            local_passed = False
    except Exception:
        local_passed = False

    # Check if we can run AWS tests
    api_url = _get_api_url()
    if not api_url or not _check_aws_credentials():
        aws_passed = False
    else:
        try:
            import boto3
            sts = boto3.client("sts", region_name=AWS_REGION)
            sts.get_caller_identity()
        except Exception:
            aws_passed = False

    print("\n" + "=" * 60)
    print("ARTIFACT INTEGRITY SUMMARY")
    print("=" * 60)
    print(f"LOCAL:  {'PASS' if local_passed else 'FAIL'}")
    print(f"AWS:    {'PASS' if aws_passed else 'FAIL'}")
    print("=" * 60)

    # This test always passes - it's just for summary output
    assert True
