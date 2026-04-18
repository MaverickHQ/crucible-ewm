"""Structured logging utilities for handlers."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation_id if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add handler name if present
        if hasattr(record, "handler"):
            log_data["handler"] = record.handler

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "msg",
                "args",
                "exc_info",
                "exc_text",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "name",
                "stack_info",
            ):
                if not key.startswith("_"):
                    log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(
    name: str,
    handler: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> logging.Logger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)
        handler: Handler name for context (e.g., "agentcore_loop", "simulate")
        correlation_id: Request correlation ID for tracing

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)

    # Add contextual info
    if handler:
        logger.handler = handler
    if correlation_id:
        logger.correlation_id = correlation_id

    return logger


def log_handler_entry(logger: logging.Logger, event: Dict[str, Any]) -> str:
    """
    Log handler entry with event data.

    Args:
        logger: Logger instance
        event: Event/payload received by handler

    Returns:
        Generated correlation_id
    """
    import uuid

    correlation_id = str(uuid.uuid4())
    logger.info(
        "Handler entry",
        extra={
            "correlation_id": correlation_id,
            "event_keys": list(event.keys()) if isinstance(event, dict) else [],
        },
    )
    return correlation_id


def log_handler_exit(
    logger: logging.Logger,
    correlation_id: str,
    response: Dict[str, Any],
    duration_ms: Optional[float] = None,
) -> None:
    """
    Log handler exit with response data.

    Args:
        logger: Logger instance
        correlation_id: Correlation ID from entry
        response: Response being returned
        duration_ms: Optional duration in milliseconds
    """
    extra = {
        "correlation_id": correlation_id,
        "response_keys": list(response.keys()) if isinstance(response, dict) else [],
    }

    if duration_ms is not None:
        extra["duration_ms"] = duration_ms

    logger.info("Handler exit", extra=extra)
