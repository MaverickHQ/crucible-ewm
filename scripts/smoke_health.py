#!/usr/bin/env python3
"""
Smoke test for /health endpoint.

This can be run locally without AWS deployment to verify the handler works.
For full integration testing with AWS, use the Lambda invocation pattern.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.aws.handlers.health_handler import handler


def main() -> int:
    """Run smoke test for health endpoint."""
    print("Running health endpoint smoke test...")
    
    # Invoke the handler directly (simulates Lambda invocation)
    result = handler({}, {})
    
    # Validate response
    if result.get("status") != "ok":
        print(f"FAIL: Expected status='ok', got '{result.get('status')}'")
        return 1
    
    if "version" not in result:
        print("FAIL: Missing 'version' in response")
        return 1
    
    if "request_id" not in result:
        print("FAIL: Missing 'request_id' in response")
        return 1
    
    print(f"Health check passed!")
    print(f"  status: {result['status']}")
    print(f"  version: {result['version']}")
    print(f"  request_id: {result['request_id']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
