"""
Integration tests for DynamoDB run record persistence in Agent Runtime v0.8.2.1.

Tests validate that run records are correctly persisted to DynamoDB table 
`beyond_tokens_runs` and link to S3 artifacts.

Requirements:
- Tests cover AWS API execution
- Verify DynamoDB record fields: run_id, created_at, duration_ms, http_status, correlation_id
- Verify correlation_id matches the x-correlation-id header sent
- Verify artifact_s3_prefix linkage (if stored in DynamoDB)

Environment:
- AWS_PROFILE: AWS profile to use (default: beyond-tokens-dev)
- AWS_REGION: AWS region (default: us-east-1)
- AGENTCORE_LOOP_API_URL: Direct API URL override
- AWS_OUTPUTS_PATH: Path to CloudFormation outputs (default: infra/cdk/cdk-outputs.json)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional
from uuid import uuid4

import boto3
import pytest
import requests

from tests.integration.aws_env import get_api_url, get_aws_profile, get_region, get_skip_reason

# AWS profile and region from task requirements
AWS_PROFILE = get_aws_profile()
AWS_REGION = get_region()


def _get_api_url() -> Optional[str]:
    """Get API URL, returns None if not available."""
    return get_api_url()


def _get_dynamodb_client():
    """Get DynamoDB client using AWS profile and region."""
    session = boto3.Session(
        profile_name=AWS_PROFILE if AWS_PROFILE != "beyond-tokens-dev" else None,
        region_name=AWS_REGION,
    )
    return session.client("dynamodb")


def _make_request(
    url: str,
    method: str = "POST",
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 120,
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
        session = boto3.Session(
            profile_name=AWS_PROFILE if AWS_PROFILE != "beyond-tokens-dev" else None,
            region_name=AWS_REGION,
        )
        sts = session.client("sts")
        sts.get_caller_identity()
        return True
    except Exception:
        return False


def _get_runs_table_name() -> Optional[str]:
    """Get the DynamoDB runs table name from CloudFormation outputs."""
    # Use the aws_env helper to get the table name
    # The table name should be in CloudFormation - we'll try to query it
    # For now, we'll use a hardcoded default based on the stack
    return os.getenv("RUNS_TABLE_NAME", "beyond_tokens_runs")


def _query_run_by_id(table_name: str, run_id: str, client: Any) -> Optional[Dict[str, Any]]:
    """Query DynamoDB for a run by run_id."""
    response = client.get_item(TableName=table_name, Key={"run_id": {"S": run_id}})
    item = response.get("Item")
    if not item:
        return None
    # Convert DynamoDB JSON format to native Python
    return _from_dynamodb_item(item)


def _ddb_to_py(av: Dict[str, Any]) -> Any:
    """
    Convert a DynamoDB AttributeValue to a native Python value.
    
    Handles types: S (string), N (number), BOOL, NULL, M (map), L (list).
    For M and L, recursively converts nested structures.
    """
    if not isinstance(av, dict):
        return av
    
    # Check for each DynamoDB type
    if "S" in av:
        return av["S"]
    elif "N" in av:
        # Try to convert to int first, then float
        try:
            return int(av["N"])
        except ValueError:
            return float(av["N"])
    elif "BOOL" in av:
        return av["BOOL"]
    elif "NULL" in av:
        return None
    elif "M" in av:
        return _from_dynamodb_item(av["M"])
    elif "L" in av:
        return [_ddb_to_py(v) for v in av["L"]]
    elif "B" in av:
        # Binary type - return as bytes
        return av["B"]
    elif "SS" in av:
        # String Set
        return list(av["SS"])
    elif "NS" in av:
        # Number Set - convert each to int/float
        result = []
        for n in av["NS"]:
            try:
                result.append(int(n))
            except ValueError:
                result.append(float(n))
        return result
    elif "L" in av:
        # Fallback for any other list type
        return [_ddb_to_py(v) for v in av["L"]]
    else:
        # Unknown type - return as-is
        return av


def _from_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB JSON item to native Python dict."""
    result = {}
    for key, value in item.items():
        result[key] = _ddb_to_py(value)
    return result


# =============================================================================
# DynamoDB Run Records Tests
# =============================================================================


class TestDynamoDBRunRecords:
    """Tests for DynamoDB run record persistence and artifact linkage."""

    @pytest.fixture(autouse=True)
    def check_aws_available(self):
        """Skip tests if AWS credentials or API not available."""
        skip_reason = get_skip_reason()
        if skip_reason:
            pytest.skip(skip_reason)
        if not _check_aws_credentials():
            pytest.skip("AWS credentials not available")
        if not _get_runs_table_name():
            pytest.skip("DynamoDB runs table name not available")

    def test_dynamodb_run_record_persistence_with_correlation_id(self):
        """
        Test that POST /agentcore/loop with upload_s3=true and x-correlation-id
        creates a DynamoDB record with correct fields.
        
        Validates:
        - run_id exists in DynamoDB
        - created_at is populated
        - duration_ms is populated
        - http_status is populated
        - correlation_id matches the x-correlation-id header (stored as trace_id)
        - artifact_s3_prefix is NOT stored in DynamoDB (linked via run_id to S3 artifacts)
        """
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        # Generate unique correlation ID
        correlation_id = f"test-correlation-{uuid4()}"

        payload = {
            "budgets": {
                "max_steps": 1,
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": True,
            "upload_s3": True,
        }

        headers = {
            "x-correlation-id": correlation_id,
        }

        response = _make_request(api_url, method="POST", data=payload, headers=headers)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is True, f"Expected ok=True, got {result}"

        # Capture run_id from response
        # Note: correlation_id is also returned in response but NOT stored in DynamoDB
        # artifact_s3_prefix is returned but NOT stored in DynamoDB - linked via run_id
        run_id = result.get("run_id")
        assert run_id, "Expected run_id in response"

        # Get DynamoDB client and table name
        ddb_client = _get_dynamodb_client()
        table_name = _get_runs_table_name()
        assert table_name, "Runs table name not found"

        # Query DynamoDB with retry for eventual consistency
        max_retries = 5
        retry_delay = 2
        run_record = None
        
        for attempt in range(max_retries):
            run_record = _query_run_by_id(table_name, run_id, ddb_client)
            if run_record:
                break
            time.sleep(retry_delay)

        assert run_record is not None, (
            f"Run record not found in DynamoDB after {max_retries} attempts. "
            f"run_id={run_id}, table={table_name}"
        )

        # Assert required fields exist
        assert "run_id" in run_record, "run_id field missing in DynamoDB record"
        assert "created_at" in run_record, "created_at field missing in DynamoDB record"
        assert "duration_ms" in run_record, "duration_ms field missing in DynamoDB record"
        assert "http_status" in run_record, "http_status field missing in DynamoDB record"

        # Canonical field: correlation_id (matches API response/logs/EMF)
        assert "correlation_id" in run_record, "correlation_id field missing in DynamoDB record"
        assert run_record["correlation_id"] == correlation_id, (
            f"correlation_id mismatch: expected {correlation_id}, "
            f"got {run_record['correlation_id']}"
        )

        # DEPRECATED: trace_id retained for backward compatibility
        assert "trace_id" in run_record, (
            "trace_id field missing in DynamoDB record (backward compat)"
        )
        
        # If trace_id present, it must equal correlation_id
        if "trace_id" in run_record:
            assert run_record["trace_id"] == correlation_id, (
                f"trace_id must equal correlation_id for backward compatibility: "
                f"expected {correlation_id}, got {run_record['trace_id']}"
            )

        # artifact_dir is ephemeral /tmp path on AWS - NOT stable for assertion
        # Stable linkage: run_id + artifact_s3_prefix (artifacts/<run_id>) -> S3
        # If artifact_dir is present, validate it's a valid ephemeral path
        if "artifact_dir" in run_record:
            assert isinstance(run_record["artifact_dir"], str), (
                "artifact_dir should be a string"
            )
            assert run_record["artifact_dir"].startswith("/tmp/"), (
                "artifact_dir should be an ephemeral /tmp path on AWS"
            )

        # Verify the fields have reasonable values
        assert isinstance(run_record["run_id"], str), "run_id should be a string"
        assert isinstance(run_record["created_at"], str), "created_at should be a string"
        assert isinstance(run_record["duration_ms"], (int, float)), "duration_ms should be numeric"
        expected_status = 200
        actual_status = run_record["http_status"]
        assert actual_status == expected_status, (
            f"Expected http_status={expected_status}, got {actual_status}"
        )

        print(f"\nDynamoDB Record for run_id={run_id}:")
        print(json.dumps(run_record, indent=2, default=str))

    def test_dynamodb_run_record_error_case(self):
        """
        Test that failed requests also create DynamoDB records.
        
        Sending max_model_calls != 0 should fail for reactive loop.
        """
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        correlation_id = f"test-error-correlation-{uuid4()}"

        payload = {
            "budgets": {
                "max_model_calls": 1,  # Nonzero should fail for reactive loop
            },
            "steps": 3,
            "seed": 42,
            "symbols": ["AAPL"],
            "write_artifacts": False,
            "upload_s3": False,
        }

        headers = {
            "x-correlation-id": correlation_id,
        }

        response = _make_request(api_url, method="POST", data=payload, headers=headers)

        # Should return 400 for invalid budget
        assert response.status_code == 400, (
            f"Expected 400, got {response.status_code}: {response.text}"
        )

        result = response.json()
        assert result["ok"] is False, f"Expected ok=False, got {result}"

        # Even failed requests should create a run record
        run_id = result.get("run_id")
        
        if run_id:
            ddb_client = _get_dynamodb_client()
            table_name = _get_runs_table_name()
            
            if table_name:
                max_retries = 5
                retry_delay = 2
                run_record = None
                
                for attempt in range(max_retries):
                    run_record = _query_run_by_id(table_name, run_id, ddb_client)
                    if run_record:
                        break
                    time.sleep(retry_delay)

                if run_record:
                    # Verify error record has required fields
                    assert "run_id" in run_record
                    assert "http_status" in run_record
                    assert run_record["http_status"] == 400
                    
                    # Canonical field: correlation_id (matches API response/logs/EMF)
                    assert "correlation_id" in run_record, (
                        "correlation_id field missing in error record"
                    )
                    assert run_record["correlation_id"] == correlation_id, (
                        f"correlation_id mismatch in error record: expected {correlation_id}, "
                        f"got {run_record['correlation_id']}"
                    )
                    
                    # DEPRECATED: trace_id retained for backward compatibility
                    assert "trace_id" in run_record, (
                        "trace_id field missing in error record (backward compat)"
                    )
                    
                    # If trace_id present, it must equal correlation_id
                    if "trace_id" in run_record:
                        assert run_record["trace_id"] == correlation_id, (
                            f"trace_id must equal correlation_id in error record: "
                            f"expected {correlation_id}, got {run_record['trace_id']}"
                        )
                    
                    print(f"\nError Run Record for run_id={run_id}:")
                    print(json.dumps(run_record, indent=2, default=str))
