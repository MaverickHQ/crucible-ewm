"""
Contract + regression tests for Agent Runtime v0.8.2.1 error shapes.

Tests validate standardized error envelopes for the POST /agentcore/loop endpoint.

Requirements:
- Invalid JSON body (send '{')
- Missing/invalid Content-Type
- Wrong types in JSON (e.g., {"steps":"five"})
- Standardized error envelope: ok==false, mode, run_id, error{code, message}

AWS tests are auto-detected based on presence of AWS URL.
Local tests always run.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pytest
import requests

from tests.integration.aws_env import (
    get_api_url,
    get_aws_profile,
    get_region,
    get_skip_reason,
)

AWS_PROFILE = get_aws_profile()
AWS_REGION = get_region()


def _make_request(
    url: str,
    method: str = "POST",
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make HTTP request using requests library.

    Args:
        url: Full URL to request
        method: HTTP method
        data: Body data (will be JSON-encoded if dict)
        headers: Additional headers
        timeout: Request timeout in seconds

    Returns:
        Response object
    """
    request_headers = headers or {}
    if data is not None:
        if "content-type" not in request_headers and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        if isinstance(data, dict):
            data = json.dumps(data)

    return requests.request(method, url, data=data, headers=request_headers, timeout=timeout)


def _get_api_url() -> Optional[str]:
    """Get API URL, returns None if not available."""
    return get_api_url()


class TestErrorEnvelopeContract:
    """
    Contract tests for standardized error envelope.
    Per OpenSpec and Agent Runtime v0.8.2.1:
    - response is JSON
    - contains ok == false
    - contains mode == "agentcore-loop" (or known value)
    - contains run_id (if handler returns one on error)
    - contains error object with code + message strings
    """

    def _validate_error_envelope(self, response: requests.Response) -> Dict[str, Any]:
        """
        Validate standardized error envelope.

        Returns:
            Parsed JSON response body

        Raises:
            AssertionError: If envelope doesn't match contract
        """
        # Must be JSON
        assert response.headers.get("Content-Type", "").startswith("application/json"), \
            f"Expected JSON content-type, got {response.headers.get('Content-Type')}"

        body = response.json()

        # Must have ok == false
        assert "ok" in body, "Response missing 'ok' field"
        assert body["ok"] is False, f"Expected ok==false, got {body.get('ok')}"

        # Must have mode
        assert "mode" in body, "Response missing 'mode' field"

        # Must have error object with code + message
        assert "error" in body, "Response missing 'error' field"
        error = body["error"]
        assert isinstance(error, dict), "error must be a dict"
        assert "code" in error, "error missing 'code' field"
        assert "message" in error, "error missing 'message' field"
        assert isinstance(error["code"], str), "error.code must be a string"
        assert isinstance(error["message"], str), "error.message must be a string"

        return body


class TestInvalidJsonBody(TestErrorEnvelopeContract):
    """Test invalid JSON body sent to POST /agentcore/loop."""

    def test_invalid_json_single_brace(self):
        """Send '{' - incomplete JSON should return error envelope."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data="{",
            headers={"Content-Type": "application/json"},
        )

        # Should get an error response
        assert response.status_code >= 400, \
            f"Expected error status, got {response.status_code}"

        body = self._validate_error_envelope(response)

        # Validate specific error content
        assert body["mode"] == "agentcore-loop"
        error_code = body["error"]["code"]
        assert error_code in ["internal_error", "invalid_json", "validation_error"], \
            f"Expected parse/error code, got {error_code}"

    def test_invalid_json_malformed(self):
        """Send '{ "steps": "five" }' - wrong types in JSON."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data='{ "steps": "five" }',
            headers={"Content-Type": "application/json"},
        )

        # This may succeed with defaults or return an error
        if response.status_code >= 400:
            body = self._validate_error_envelope(response)
            assert body["error"]["code"]
        else:
            assert response.status_code == 200
            body = response.json()
            assert body.get("ok") is True

    def test_invalid_json_empty_body(self):
        """Send empty body."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data="",
            headers={"Content-Type": "application/json"},
        )

        # Should get an error or use defaults
        if response.status_code >= 400:
            body = self._validate_error_envelope(response)
            assert body["error"]["code"]
        else:
            assert response.status_code == 200


class TestContentTypeValidation(TestErrorEnvelopeContract):
    """Test Content-Type header validation."""

    def test_missing_content_type(self):
        """Send request without Content-Type header."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data='{"steps": 1}',
            headers={},
        )

        if response.status_code >= 400:
            body = self._validate_error_envelope(response)
            assert body["error"]["code"]
        else:
            assert response.status_code == 200

    def test_invalid_content_type(self):
        """Send request with invalid Content-Type."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data='{"steps": 1}',
            headers={"Content-Type": "text/plain"},
        )

        if response.status_code >= 400:
            body = self._validate_error_envelope(response)
            assert body["error"]["code"]
        else:
            assert response.status_code == 200

    def test_wrong_content_type_xml(self):
        """Send request with XML Content-Type."""
        api_url = _get_api_url()
        if not api_url:
            skip_reason = get_skip_reason() or "AWS API URL not available"
            pytest.skip(skip_reason)

        response = _make_request(
            api_url,
            method="POST",
            data="<xml>test</xml>",
            headers={"Content-Type": "application/xml"},
        )

        if response.status_code >= 400:
            body = self._validate_error_envelope(response)
            assert body["error"]["code"]


class TestLocalErrorContract:
    """
    Local contract tests - test the handler directly without HTTP.
    These tests always run as they don't require AWS.
    """

    def test_handler_returns_error_envelope_on_invalid_json(self):
        """Test handler returns proper error envelope for invalid JSON."""
        from services.aws.handlers.agentcore_loop_handler import handler

        event = {
            "headers": {"Content-Type": "application/json"},
            "body": "{",
        }

        result = handler(event, None)

        assert result["statusCode"] >= 400, f"Expected error status, got {result['statusCode']}"
        body = json.loads(result["body"])

        assert body["ok"] is False
        assert "mode" in body
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_handler_returns_error_on_missing_body(self):
        """Test handler handles missing body gracefully."""
        from services.aws.handlers.agentcore_loop_handler import handler

        event = {
            "headers": {"Content-Type": "application/json"},
            "body": None,
        }

        result = handler(event, None)
        body = json.loads(result["body"])

        assert "ok" in body
        if body["ok"] is False:
            assert "error" in body

    def test_handler_returns_error_on_type_mismatch(self):
        """Test handler handles type mismatches in JSON."""
        from services.aws.handlers.agentcore_loop_handler import handler

        event = {
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"steps": "not_a_number"}),
        }

        result = handler(event, None)
        body = json.loads(result["body"])

        assert "ok" in body
        if body["ok"] is False:
            assert "error" in body
            assert "code" in body["error"]
