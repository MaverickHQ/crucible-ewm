"""Unit tests for structured logging."""

from __future__ import annotations

import json
import logging

from services.core.logging import (
    StructuredFormatter,
    get_logger,
    log_handler_entry,
    log_handler_exit,
)


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    def test_format_includes_timestamp(self):
        """Test that formatted log includes timestamp."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        formatter = StructuredFormatter()
        result = formatter.format(record)

        parsed = json.loads(result)
        assert "timestamp" in parsed

    def test_format_includes_level(self):
        """Test that formatted log includes level."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        formatter = StructuredFormatter()
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["level"] == "INFO"

    def test_format_includes_message(self):
        """Test that formatted log includes message."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        formatter = StructuredFormatter()
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["message"] == "test message"

    def test_format_includes_correlation_id(self):
        """Test that formatted log includes correlation_id when present."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-correlation-id"

        formatter = StructuredFormatter()
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["correlation_id"] == "test-correlation-id"

    def test_format_includes_handler_context(self):
        """Test that formatted log includes handler context when present."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.handler = "agentcore_loop"

        formatter = StructuredFormatter()
        result = formatter.format(record)

        parsed = json.loads(result)
        assert parsed["handler"] == "agentcore_loop"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_handler_name(self):
        """Test that get_logger accepts handler name."""
        logger = get_logger("test", handler="simulate")
        assert hasattr(logger, "handler")
        assert logger.handler == "simulate"

    def test_get_logger_with_correlation_id(self):
        """Test that get_logger accepts correlation_id."""
        logger = get_logger("test", correlation_id="abc-123")
        assert hasattr(logger, "correlation_id")
        assert logger.correlation_id == "abc-123"


class TestLogHandlerEntry:
    """Tests for log_handler_entry function."""

    def test_log_handler_entry_returns_correlation_id(self):
        """Test that log_handler_entry returns a correlation_id."""
        logger = logging.getLogger("test_entry")
        logger.setLevel(logging.INFO)

        # Suppress output during test
        handler = logging.NullHandler()
        logger.addHandler(handler)

        correlation_id = log_handler_entry(logger, {"key": "value"})
        assert isinstance(correlation_id, str)
        assert len(correlation_id) > 0


class TestLogHandlerExit:
    """Tests for log_handler_exit function."""

    def test_log_handler_exit_logs_response(self):
        """Test that log_handler_exit logs response keys."""
        logger = logging.getLogger("test_exit")
        logger.setLevel(logging.INFO)

        # Suppress output during test
        handler = logging.NullHandler()
        logger.addHandler(handler)

        # Should not raise
        log_handler_exit(
            logger,
            correlation_id="test-id",
            response={"key": "value"},
        )

    def test_log_handler_exit_with_duration(self):
        """Test that log_handler_exit includes duration."""
        logger = logging.getLogger("test_duration")
        logger.setLevel(logging.INFO)

        # Suppress output during test
        handler = logging.NullHandler()
        logger.addHandler(handler)

        # Should not raise
        log_handler_exit(
            logger,
            correlation_id="test-id",
            response={"key": "value"},
            duration_ms=150.5,
        )
