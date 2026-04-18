"""
Standardized error handling for API responses.

Per OpenSpec API contract (openspec/specs/api/spec.md):
- Error responses must include: code, message, details, request_id
- All fields are required (details can be empty object)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class APIError:
    """Standardized API error structure per OpenSpec."""

    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None

    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": self.request_id,
            }
        }


def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized error response per OpenSpec API contract.

    Args:
        code: Error code (e.g., "invalid_request", "internal_error")
        message: Human-readable error message
        details: Additional error details (default: empty dict)
        request_id: Request tracking ID (auto-generated if not provided)

    Returns:
        Dict with standardized error structure
    """
    return APIError(
        code=code,
        message=message,
        details=details or {},
        request_id=request_id,
    ).to_dict()


def create_validation_error(
    message: str,
    field_errors: Optional[Dict[str, str]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a validation error response."""
    details = {}
    if field_errors:
        details["field_errors"] = field_errors

    return create_error_response(
        code="validation_error",
        message=message,
        details=details,
        request_id=request_id,
    )


def create_not_found_error(
    resource: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a not found error response."""
    return create_error_response(
        code="not_found",
        message=f"{resource} not found",
        request_id=request_id,
    )


def create_internal_error(
    message: str = "An internal error occurred",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an internal server error response."""
    return create_error_response(
        code="internal_error",
        message=message,
        request_id=request_id,
    )
