"""
AWS Environment Resolution Helper for Integration Tests.

This module provides utilities to resolve AWS environment configuration for
integration tests without depending on local CDK outputs files.

Resolution Order:
1. AGENTCORE_LOOP_API_URL env var (if set)
2. CloudFormation stack output (BeyondTokensStack → AgentCoreLoopApiUrl)
3. If neither is available, pytest should SKIP AWS tests with a clear message.

Uses AWS CLI via subprocess to query CloudFormation outputs.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Optional, Tuple  # noqa: UP035

import pytest

# =============================================================================
# Configuration Getters
# =============================================================================


def get_region() -> str:
    """Get AWS region from environment variable or default to us-east-1."""
    return os.getenv("AWS_REGION", "us-east-1")


def get_stack_name() -> str:
    """Get CloudFormation stack name from env var or default to BeyondTokensStack."""
    return os.getenv("BEYOND_TOKENS_STACK_NAME", "BeyondTokensStack")


def get_aws_profile() -> str:
    """Get AWS profile from environment variable or default to beyond-tokens-dev."""
    return os.getenv("AWS_PROFILE", "beyond-tokens-dev")


# =============================================================================
# CloudFormation Output Resolution
# =============================================================================


def _query_cloudformation_outputs(region: str, stack_name: str) -> dict:
    """
    Query CloudFormation stack outputs using AWS CLI.

    Args:
        region: AWS region
        stack_name: CloudFormation stack name

    Returns:
        Dict of output key -> value

    Raises:
        subprocess.CalledProcessError: If AWS CLI fails
        json.JSONDecodeError: If response is not valid JSON
    """
    result = subprocess.run(
        [
            "aws", "cloudformation", "describe-stacks",
            "--region", region,
            "--stack-name", stack_name,
            "--query", "Stacks[0].Outputs",
            "--output", "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    outputs = json.loads(result.stdout)
    # Convert to dict: {OutputKey: OutputValue}
    return {output["OutputKey"]: output["OutputValue"] for output in outputs}


def _try_cloudformation_lookup(region: str, stack_name: str) -> Optional[dict]:
    """
    Try to lookup CloudFormation outputs, return None if stack doesn't exist.

    Returns:
        Dict of outputs or None if stack not found
    """
    try:
        return _query_cloudformation_outputs(region, stack_name)
    except subprocess.CalledProcessError as e:
        # Stack might not exist
        if "Stack with id" in e.stderr and "does not exist" in e.stderr:
            return None
        raise
    except Exception:
        # Other errors (no credentials, network issues, etc.)
        return None


# =============================================================================
# API URL Resolution
# =============================================================================


def resolve_api_url() -> Tuple[Optional[str], str]:
    """
    Resolve the AgentCore Loop API URL.

    Resolution order:
    1. AGENTCORE_LOOP_API_URL env var (if set)
    2. CloudFormation stack output (BeyondTokensStack → AgentCoreLoopApiUrl)

    Returns:
        Tuple of (api_url or None, reason string)
        - If URL found: (url, "resolved from <source>")
        - If URL not found: (None, "reason why not found")
    """
    # Priority 1: Direct env var
    api_url = os.getenv("AGENTCORE_LOOP_API_URL")
    if api_url:
        return api_url, "resolved from AGENTCORE_LOOP_API_URL env var"

    # Priority 2: CloudFormation stack
    region = get_region()
    stack_name = get_stack_name()

    try:
        outputs = _try_cloudformation_lookup(region, stack_name)
        if outputs:
            url = outputs.get("AgentCoreLoopApiUrl")
            if url:
                return url, f"resolved from CloudFormation stack {stack_name} output"

        return None, (
            f"CloudFormation stack '{stack_name}' exists but "
            f"AgentCoreLoopApiUrl output not found. "
            f"Deploy BeyondTokensStack or set AGENTCORE_LOOP_API_URL."
        )
    except Exception as e:
        return None, (
            f"Failed to query CloudFormation stack {stack_name}: {e}. "
            f"Set AGENTCORE_LOOP_API_URL env var or deploy BeyondTokensStack."
        )


def get_api_url() -> Optional[str]:
    """
    Get the API URL for testing.

    Returns:
        Full API URL with /agentcore/loop path, or None if not available.
    """
    url, _ = resolve_api_url()
    if not url:
        return None
    if url.endswith("/agentcore/loop"):
        return url
    return f"{url}/agentcore/loop"


def get_skip_reason() -> Optional[str]:
    """
    Get the reason why AWS tests should be skipped.

    Returns:
        Skip reason string if AWS not available, None if AWS is available.
    """
    url, reason = resolve_api_url()
    if url:
        return None  # AWS is available
    return f"AWS API URL not available: {reason}"


# =============================================================================
# Artifacts Bucket Resolution
# =============================================================================


def resolve_artifacts_bucket() -> Tuple[Optional[str], str]:
    """
    Resolve the artifacts S3 bucket name.

    Resolution order:
    1. ARTIFACT_BUCKET env var (if set)
    2. CloudFormation stack output (BeyondTokensStack → ArtifactsBucketName)

    Returns:
        Tuple of (bucket_name or None, reason string)
    """
    # Priority 1: Direct env var
    bucket = os.getenv("ARTIFACT_BUCKET")
    if bucket:
        return bucket, "resolved from ARTIFACT_BUCKET env var"

    # Priority 2: CloudFormation stack
    region = get_region()
    stack_name = get_stack_name()

    try:
        outputs = _try_cloudformation_lookup(region, stack_name)
        if outputs:
            bucket = outputs.get("ArtifactsBucketName")
            if bucket:
                return bucket, f"resolved from CloudFormation stack {stack_name} output"

        return None, (
            f"CloudFormation stack '{stack_name}' exists but "
            f"ArtifactsBucketName output not found. "
            f"Set ARTIFACT_BUCKET env var or deploy BeyondTokensStack."
        )
    except Exception as e:
        return None, (
            f"Failed to query CloudFormation stack {stack_name}: {e}. "
            f"Set ARTIFACT_BUCKET env var."
        )


# =============================================================================
# pytest Integration
# =============================================================================


def skip_if_no_aws(reason: Optional[str] = None):
    """
    pytest skip marker for when AWS is not available.

    Usage:
        @skip_if_no_aws()
        def test_aws_something():
            ...

    Or at module level:
        pytest.skip(skip_if_no_aws(), allow_module_level=True)
    """
    skip_reason = get_skip_reason()
    if skip_reason:
        if reason:
            return pytest.skip(f"{skip_reason}. {reason}", allow_module_level=True)
        return pytest.skip(skip_reason, allow_module_level=True)
    return None


def require_aws(f):
    """
    Decorator to skip test if AWS is not available.

    Usage:
        @require_aws
        def test_aws_something():
            ...
    """
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        return f(*args, **kwargs)

    return wrapper
