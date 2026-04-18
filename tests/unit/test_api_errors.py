"""Unit tests for standardized API error handling."""

from __future__ import annotations

from services.core.errors import (
    APIError,
    create_error_response,
    create_internal_error,
    create_not_found_error,
    create_validation_error,
)


class TestAPIError:
    """Tests for the APIError dataclass."""

    def test_api_error_to_dict(self):
        """Test APIError converts to correct dictionary format."""
        error = APIError(code="test_code", message="test message")
        result = error.to_dict()

        assert "error" in result
        assert result["error"]["code"] == "test_code"
        assert result["error"]["message"] == "test message"
        assert result["error"]["details"] == {}
        assert "request_id" in result["error"]

    def test_api_error_with_details(self):
        """Test APIError includes details."""
        error = APIError(
            code="validation_error",
            message="Invalid input",
            details={"field": "name", "reason": "required"},
        )
        result = error.to_dict()

        assert result["error"]["details"]["field"] == "name"
        assert result["error"]["details"]["reason"] == "required"

    def test_api_error_generates_request_id(self):
        """Test APIError auto-generates request_id if not provided."""
        error = APIError(code="test", message="test")
        result = error.to_dict()

        assert result["error"]["request_id"] is not None
        assert len(result["error"]["request_id"]) > 0


class TestCreateErrorResponse:
    """Tests for create_error_response helper function."""

    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        result = create_error_response("invalid_request", "Invalid request")

        assert result["error"]["code"] == "invalid_request"
        assert result["error"]["message"] == "Invalid request"
        assert result["error"]["details"] == {}
        assert "request_id" in result["error"]

    def test_create_error_response_with_details(self):
        """Test error response with details."""
        result = create_error_response(
            code="invalid_request", message="Invalid request", details={"field": "run_id"}
        )

        assert result["error"]["details"]["field"] == "run_id"

    def test_create_error_response_with_custom_request_id(self):
        """Test error response with custom request_id."""
        result = create_error_response(
            code="invalid_request", message="Invalid request", request_id="custom-request-id"
        )

        assert result["error"]["request_id"] == "custom-request-id"


class TestCreateValidationError:
    """Tests for create_validation_error helper."""

    def test_create_validation_error_basic(self):
        """Test basic validation error."""
        result = create_validation_error("Validation failed")

        assert result["error"]["code"] == "validation_error"
        assert result["error"]["message"] == "Validation failed"

    def test_create_validation_error_with_field_errors(self):
        """Test validation error with field errors."""
        result = create_validation_error(
            "Validation failed", field_errors={"name": "required", "age": "must be positive"}
        )

        assert result["error"]["code"] == "validation_error"
        assert result["error"]["details"]["field_errors"]["name"] == "required"
        assert result["error"]["details"]["field_errors"]["age"] == "must be positive"


class TestCreateNotFoundError:
    """Tests for create_not_found_error helper."""

    def test_create_not_found_error(self):
        """Test not found error."""
        result = create_not_found_error("Run")

        assert result["error"]["code"] == "not_found"
        assert result["error"]["message"] == "Run not found"


class TestCreateInternalError:
    """Tests for create_internal_error helper."""

    def test_create_internal_error_default_message(self):
        """Test internal error with default message."""
        result = create_internal_error()

        assert result["error"]["code"] == "internal_error"
        assert result["error"]["message"] == "An internal error occurred"

    def test_create_internal_error_custom_message(self):
        """Test internal error with custom message."""
        result = create_internal_error("Database connection failed")

        assert result["error"]["code"] == "internal_error"
        assert result["error"]["message"] == "Database connection failed"
