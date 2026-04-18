"""
Contract tests for API compliance with OpenSpec.

Per openspec/specs/api/spec.md:
- GET /health: returns status (must be "ok") and version (semantic version)
- Error responses: code, message, details, request_id all required
"""

from __future__ import annotations

from services.aws.handlers.health_handler import handler as health_handler
from ewm_core.errors import create_error_response, create_validation_error


class TestHealthEndpointContract:
    """Contract tests for GET /health endpoint per OpenSpec."""

    def test_health_status_is_ok(self):
        """Per OpenSpec: status must be 'ok'"""
        result = health_handler({}, {})
        assert result["status"] == "ok"

    def test_health_has_version(self):
        """Per OpenSpec: version is required and must be string"""
        result = health_handler({}, {})
        assert "version" in result
        assert isinstance(result["version"], str)

    def test_health_version_is_semantic(self):
        """Per OpenSpec: version should follow semantic versioning"""
        result = health_handler({}, {})
        version = result["version"]
        parts = version.split(".")
        assert len(parts) >= 2
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' is not a number"


class TestErrorResponseContract:
    """Contract tests for error responses per OpenSpec."""

    def test_error_has_required_fields(self):
        """Per OpenSpec: error must have code, message, details, request_id"""
        result = create_error_response("test_code", "test message")

        assert "error" in result
        error = result["error"]

        assert "code" in error
        assert "message" in error
        assert "details" in error
        assert "request_id" in error

    def test_error_code_is_string(self):
        """Per OpenSpec: code must be a string"""
        result = create_error_response("invalid_request", "Invalid request")
        assert isinstance(result["error"]["code"], str)

    def test_error_message_is_string(self):
        """Per OpenSpec: message must be a string"""
        result = create_error_response("invalid_request", "Invalid request")
        assert isinstance(result["error"]["message"], str)

    def test_error_details_is_object(self):
        """Per OpenSpec: details must be an object (dict)"""
        result = create_error_response("invalid_request", "Invalid request")
        assert isinstance(result["error"]["details"], dict)

    def test_error_details_can_be_empty(self):
        """Per OpenSpec: details can be empty object"""
        result = create_error_response("invalid_request", "Invalid request")
        assert result["error"]["details"] == {}

    def test_error_request_id_is_string(self):
        """Per OpenSpec: request_id must be a string"""
        result = create_error_response("invalid_request", "Invalid request")
        assert isinstance(result["error"]["request_id"], str)
        assert len(result["error"]["request_id"]) > 0

    def test_error_with_details(self):
        """Per OpenSpec: details can contain additional info"""
        result = create_error_response(
            "validation_error",
            "Validation failed",
            details={"field": "run_id", "reason": "required"},
        )

        assert result["error"]["details"]["field"] == "run_id"
        assert result["error"]["details"]["reason"] == "required"


class TestValidationErrorContract:
    """Contract tests for validation errors."""

    def test_validation_error_structure(self):
        """Validation errors must follow OpenSpec contract"""
        result = create_validation_error("Invalid input", field_errors={"name": "required"})

        assert "error" in result
        assert result["error"]["code"] == "validation_error"
        assert "field_errors" in result["error"]["details"]
        assert result["error"]["details"]["field_errors"]["name"] == "required"


class TestContractSmokeTest:
    """Smoke test for contract compliance."""

    def test_health_endpoint_smoke(self):
        """Quick smoke test for health endpoint"""
        result = health_handler({}, {})
        assert result["status"] == "ok"
        assert "version" in result

    def test_error_response_smoke(self):
        """Quick smoke test for error responses"""
        result = create_error_response("test", "test")
        assert "error" in result
        assert "request_id" in result["error"]
