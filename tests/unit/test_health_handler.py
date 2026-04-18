from __future__ import annotations

from services.aws.handlers.health_handler import handler


class TestHealthHandler:
    """Unit tests for the health endpoint handler."""

    def test_health_returns_ok_status(self):
        """Test that health endpoint returns 'ok' status."""
        result = handler({}, {})

        assert result["status"] == "ok"

    def test_health_returns_version(self):
        """Test that health endpoint returns version field."""
        result = handler({}, {})

        assert "version" in result
        assert isinstance(result["version"], str)

    def test_health_returns_request_id(self):
        """Test that health endpoint returns request_id for traceability."""
        result = handler({}, {})

        assert "request_id" in result
        assert isinstance(result["request_id"], str)
        assert len(result["request_id"]) > 0

    def test_health_response_shape(self):
        """Test that health response has correct shape per OpenSpec."""
        result = handler({}, {})

        # Required fields per OpenSpec
        assert "status" in result
        assert "version" in result

        # Additional field for traceability
        assert "request_id" in result

    def test_health_status_is_exactly_ok(self):
        """Test that status field is exactly 'ok' per OpenSpec."""
        result = handler({}, {})

        assert result["status"] == "ok"

    def test_health_version_format(self):
        """Test that version follows semantic versioning."""
        result = handler({}, {})

        version = result["version"]
        # Check basic semantic version format (x.y.z)
        parts = version.split(".")
        assert len(parts) >= 2
        for part in parts:
            assert part.isdigit()
