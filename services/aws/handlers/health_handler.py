from __future__ import annotations

import os
import uuid

# Version from pyproject.toml - in production this would be imported
API_VERSION = os.environ.get("API_VERSION", "0.8.5")


def handler(event, context):
    """
    Health check endpoint handler.

    Returns:
        dict: Health status with status and version fields
    """
    # Generate request_id for traceability
    request_id = str(uuid.uuid4())

    return {"status": "ok", "version": API_VERSION, "request_id": request_id}
