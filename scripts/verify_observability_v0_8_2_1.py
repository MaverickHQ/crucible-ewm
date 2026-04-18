#!/usr/bin/env python3
"""
Observability verification script for v0.8.2.1

Validates:
- correlation_id appears in grep-friendly logs and structured JSON
- EMF metrics emit Requests/LatencyMs
- Error path increments ClientErrors or ServerErrors (depending on classification)

Error classification:
- ClientErrors: 400 <= http_status < 500 (client-side errors like bad request)
- ServerErrors: http_status >= 500 (server-side errors like internal errors)

CLI-first design using AWS CLI (no boto3), curl for HTTP.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "beyond-tokens-dev")

# Stack outputs (can be overridden by env vars)
AGENT_CORE_LOOP_API_URL = os.environ.get("AGENTCORE_LOOP_API_URL")
AGENT_CORE_LOOP_FUNCTION_NAME = os.environ.get("AGENT_CORE_LOOP_FUNCTION_NAME")

# Namespace for EMF metrics
METRIC_NAMESPACE = "BeyondTokens/AgentCoreLoop"


def check_aws_cli() -> None:
    """Verify AWS CLI is available and credentials are valid."""
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            env={**os.environ, "AWS_PROFILE": AWS_PROFILE, "AWS_REGION": AWS_REGION},
        )
        if result.returncode != 0:
            print(f"ERROR: AWS CLI credentials check failed:")
            print(f"  stderr: {result.stderr}")
            sys.exit(1)
        # Parse JSON to verify credentials work
        try:
            identity = json.loads(result.stdout)
            print(f"  AWS Identity: {identity.get('Arn', 'unknown')}")
        except json.JSONDecodeError:
            print(f"ERROR: Could not parse AWS STS response")
            sys.exit(1)
    except FileNotFoundError:
        print("ERROR: AWS CLI (aws) not found. Please install AWS CLI.")
        sys.exit(1)


def run_aws_command(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run AWS CLI command with environment set."""
    env = {**os.environ, "AWS_PROFILE": AWS_PROFILE, "AWS_REGION": AWS_REGION}
    return subprocess.run(
        ["aws"] + args,
        capture_output=True,
        text=True,
        env=env,
        check=check,
    )


def _stack_output(key: str) -> str | None:
    """Get CloudFormation stack output value using AWS CLI."""
    try:
        result = run_aws_command([
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            "BeyondTokensStack",
            "--query",
            f"Stacks[0].Outputs[?OutputKey=='{key}'].OutputValue | [0]",
            "--output",
            "text",
        ])
        out = result.stdout.strip()
        return out if out and out != "None" else None
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        print("ERROR: AWS CLI not found")
        sys.exit(1)


def get_api_url() -> str:
    """Get the AgentCore Loop API URL."""
    if AGENT_CORE_LOOP_API_URL:
        return AGENT_CORE_LOOP_API_URL
    
    # Try CFN outputs
    url = _stack_output("AgentCoreLoopApiUrl") or _stack_output("AgentCoreHelloApiUrl")
    if url:
        return url
    
    raise RuntimeError("Could not resolve AgentCoreLoopApiUrl from env or CloudFormation outputs.")


def get_lambda_function_name() -> str:
    """Get the AgentCore Loop Lambda function name."""
    if AGENT_CORE_LOOP_FUNCTION_NAME:
        return AGENT_CORE_LOOP_FUNCTION_NAME
    
    # Try CFN outputs
    name = _stack_output("AgentCoreLoopFunctionName")
    if name:
        return name
    
    raise RuntimeError("Could not resolve AgentCoreLoopFunctionName from env or CloudFormation outputs.")


def generate_correlation_id(prefix: str = "obs") -> str:
    """Generate a correlation ID: obs-<timestamp>-<rand>"""
    timestamp = int(time.time())
    rand = random.randint(1000, 9999)
    return f"{prefix}-{timestamp}-{rand}"


def query_cloudwatch_logs(
    log_group_name: str,
    correlation_id: str,
    start_time_ms: int,
    end_time_ms: int,
) -> list[dict[str, Any]]:
    """
    Query CloudWatch logs using AWS CLI filter-log-events.
    
    Returns:
        list: matched events containing the correlation_id
    """
    # Use filter-log-events with filter pattern matching correlation_id
    # The filter pattern should match the grep-friendly line: correlation_id=<CID>
    filter_pattern = f'"{correlation_id}"'
    
    try:
        result = run_aws_command([
            "logs",
            "filter-log-events",
            "--log-group-name", log_group_name,
            "--start-time", str(start_time_ms),
            "--end-time", str(end_time_ms),
            "--filter-pattern", filter_pattern,
            "--limit", "10000",
            "--output", "json",
        ])
        
        events = json.loads(result.stdout).get("events", [])
        return events
        
    except subprocess.CalledProcessError as e:
        print(f"  AWS CLI error: {e.stderr}")
        raise
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  stdout: {result.stdout}")
        raise


def check_correlation_id_in_logs(
    log_group_name: str,
    correlation_id: str,
    test_start_time: datetime,
) -> tuple[bool, list[str], int, int]:
    """
    Check if correlation_id appears in CloudWatch logs.
    
    Uses a wide time window: start_time = now - 10 minutes, end_time = now + 1 minute
    Implements retry/backoff logic (up to 10 retries with 2s, 3s, 5s, 8s, 10s... capped at 10s).
    
    Returns:
        tuple: (found, messages, attempts, events_checked)
    """
    # Calculate time window
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=10)
    window_end = now + timedelta(minutes=1)
    
    # Convert to milliseconds for CloudWatch
    start_time_ms = int(window_start.timestamp() * 1000)
    end_time_ms = int(window_end.timestamp() * 1000)
    
    print(f"\n  Searching for correlation_id: {correlation_id}")
    print(f"  Test start time (for reference): {test_start_time.isoformat()}")
    print(f"  Time window: {start_time_ms} to {end_time_ms}")
    print(f"  (Human readable: {datetime.fromtimestamp(start_time_ms/1000, tz=timezone.utc).isoformat()} to {datetime.fromtimestamp(end_time_ms/1000, tz=timezone.utc).isoformat()})")
    
    # Retry schedule: 2s, 3s, 5s, 8s, 10s, 10s, 10s, 10s, 10s, 10s
    sleep_schedule = [2, 3, 5, 8, 10, 10, 10, 10, 10, 10]
    max_retries = 10
    
    print(f"  Max retries: {max_retries}")
    print(f"  Sleep schedule: {sleep_schedule}")
    
    for attempt in range(max_retries):
        print(f"\n  Attempt {attempt + 1}/{max_retries}:")
        
        try:
            # Query CloudWatch logs using AWS CLI
            events = query_cloudwatch_logs(
                log_group_name=log_group_name,
                correlation_id=correlation_id,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
            )
            
            print(f"    Found {len(events)} events matching filter pattern")
            
            # Now search for the specific patterns in the events
            matched_events = []
            for event in events:
                message = event.get("message", "")
                
                # Pattern 1: correlation_id=<CID> (grep-friendly)
                if f"correlation_id={correlation_id}" in message:
                    matched_events.append(event)
                    continue
                
                # Pattern 2: JSON log with "correlation_id":"<CID>"
                try:
                    log_data = json.loads(message)
                    if isinstance(log_data, dict):
                        cid = log_data.get("correlation_id")
                        if cid == correlation_id:
                            matched_events.append(event)
                except json.JSONDecodeError:
                    pass
            
            if matched_events:
                print(f"    ✅ Found {len(matched_events)} events with correlation_id={correlation_id}")
                messages = [event.get("message", "") for event in matched_events]
                return True, messages, attempt + 1, len(events)
            
            print(f"    ⏳ No match found yet")
            
            # If no match found and not last retry, wait before retrying
            if attempt < max_retries - 1:
                sleep_time = sleep_schedule[attempt]
                print(f"    Sleeping {sleep_time}s before retry...")
                time.sleep(sleep_time)
                
        except Exception as e:
            print(f"    Error: {e}")
            if attempt < max_retries - 1:
                sleep_time = sleep_schedule[attempt]
                print(f"    Sleeping {sleep_time}s before retry...")
                time.sleep(sleep_time)
            else:
                raise
    
    return False, [], max_retries, 0


def check_emf_in_logs(
    log_group_name: str,
    start_time: datetime,
) -> tuple[dict[str, bool], list[dict]]:
    """Check for EMF metrics in CloudWatch logs using AWS CLI."""
    # Calculate time window: start_time - 10 minutes to now + 1 minute
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=10)
    window_end = now + timedelta(minutes=1)
    
    start_ms = int(window_start.timestamp() * 1000)
    end_ms = int(window_end.timestamp() * 1000)
    
    print(f"\n  Checking for EMF metrics in logs...")
    print(f"  Time window: {start_ms} to {end_ms}")
    
    try:
        # Query for EMF entries (look for _aws indicator)
        result = run_aws_command([
            "logs",
            "filter-log-events",
            "--log-group-name", log_group_name,
            "--start-time", str(start_ms),
            "--end-time", str(end_ms),
            "--filter-pattern", '"_aws"',
            "--limit", "10000",
            "--output", "json",
        ])
        
        events = json.loads(result.stdout).get("events", [])
        print(f"  Found {len(events)} events with EMF indicator")
        
        results = {
            "Requests": False,
            "LatencyMs": False,
            "ClientErrors": False,
            "ServerErrors": False,
        }
        
        emf_entries = []
        for event in events:
            try:
                message = event.get("message", "")
                log_data = json.loads(message)
                emf_entries.append(log_data)
                
                # Check for required metrics
                if "Requests" in log_data:
                    results["Requests"] = True
                if "LatencyMs" in log_data:
                    results["LatencyMs"] = True
                if "ClientErrors" in log_data:
                    results["ClientErrors"] = True
                if "ServerErrors" in log_data:
                    results["ServerErrors"] = True
            except json.JSONDecodeError:
                continue
        
        return results, emf_entries
        
    except Exception as e:
        print(f"  Error checking EMF metrics: {e}")
        return {
            "Requests": False,
            "LatencyMs": False,
            "ClientErrors": False,
            "ServerErrors": False,
        }, []


def make_curl_request(
    url: str,
    correlation_id: str,
    payload: dict[str, Any],
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    """Make API request using curl with correlation ID header."""
    import shlex
    
    # Build curl command
    cmd = [
        "curl",
        "-s",  # Silent
        "-w", "%{http_code}",  # Write out HTTP status code
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", f"x-correlation-id: {correlation_id}",
        "-d", json.dumps(payload),
        "--connect-timeout", str(timeout),
        "--max-time", str(timeout),
    ]
    
    # Add CA bundle if available
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    if ca_bundle:
        cmd.extend(["--cacert", ca_bundle])
    else:
        # Try to use certifi bundle
        try:
            import certifi
            cmd.extend(["--cacert", certifi.where()])
        except ImportError:
            pass
    
    cmd.append(url)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        
        # Extract status code (last 3 characters) and body
        output = result.stdout
        if len(output) >= 3:
            status_code = int(output[-3:])
            body_str = output[:-3]
        else:
            status_code = 0
            body_str = output
        
        try:
            body = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            body = {"raw": body_str}
        
        return status_code, body
        
    except subprocess.TimeoutExpired:
        return 0, {"error": "Request timed out"}
    except Exception as e:
        return 0, {"error": str(e)}


def force_error_request(
    url: str,
    correlation_id: str,
    error_type: str = "invalid_json",
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    """Force an error by sending invalid payload using curl."""
    import shlex
    
    headers = [
        "-H", "Content-Type: application/json",
        "-H", f"x-correlation-id: {correlation_id}",
    ]
    
    # Add CA bundle if available
    cmd = [
        "curl",
        "-s",
        "-w", "%{http_code}",
        "-X", "POST",
    ]
    
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    if ca_bundle:
        cmd.extend(["--cacert", ca_bundle])
    else:
        try:
            import certifi
            cmd.extend(["--cacert", certifi.where()])
        except ImportError:
            pass
    
    cmd.extend(headers)
    
    if error_type == "invalid_json":
        # Send malformed JSON in the body
        payload = "{ invalid json }"
        cmd.extend(["-d", payload])
    elif error_type == "budget_violation":
        # Send budget that will cause an error
        payload = json.dumps({
            "mode": "agentcore-loop",
            "seed": 7,
            "symbols": ["INVALID_SYMBOL_THAT_CAUSE_ERROR"],
            "starting_cash": 1000.0,
            "steps": 5,
            "budgets": {
                "max_steps": -1,  # Invalid budget
                "max_tool_calls": 10,
            },
        })
        cmd.extend(["-d", payload])
    else:
        # Default: send empty body to trigger validation error
        payload = json.dumps({})
        cmd.extend(["-d", payload])
    
    cmd.extend(["--connect-timeout", str(timeout), "--max-time", str(timeout)])
    cmd.append(url)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        
        output = result.stdout
        if len(output) >= 3:
            status_code = int(output[-3:])
            body_str = output[:-3]
        else:
            status_code = 0
            body_str = output
        
        try:
            body = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            body = {"raw": body_str}
        
        return status_code, body
        
    except subprocess.TimeoutExpired:
        return 0, {"error": "Request timed out"}
    except Exception as e:
        return 0, {"error": str(e)}


def main() -> int:
    """Main verification routine."""
    print("=" * 60)
    print("Observability Verification for v0.8.2.1")
    print("=" * 60)
    
    # Check AWS CLI and credentials first
    print("\nChecking AWS CLI and credentials...")
    check_aws_cli()
    print("  ✅ AWS CLI OK")
    
    # Get configuration
    api_url = get_api_url()
    lambda_name = get_lambda_function_name()
    log_group_name = f"/aws/lambda/{lambda_name}"
    
    print(f"\nConfiguration:")
    print(f"  API URL: {api_url}")
    print(f"  Lambda Function: {lambda_name}")
    print(f"  Log Group: {log_group_name}")
    print(f"  AWS Profile: {AWS_PROFILE}")
    print(f"  AWS Region: {AWS_REGION}")
    
    # Test 1: Normal request with correlation ID
    print("\n" + "-" * 60)
    print("TEST 1: Normal Request with Correlation ID")
    print("-" * 60)
    
    cid1 = generate_correlation_id("obs")
    print(f"  Correlation ID: {cid1}")
    
    # Record start time for log queries
    test1_start = datetime.now(timezone.utc)
    
    payload = {
        "mode": "agentcore-loop",
        "seed": 7,
        "symbols": ["AAPL", "MSFT"],
        "starting_cash": 1000.0,
        "steps": 3,
        "budgets": {
            "max_steps": 3,
            "max_tool_calls": 20,
            "max_model_calls": 0,
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        },
    }
    
    url = api_url.rstrip("/") + "/agentcore/loop"
    status1, body1 = make_curl_request(url, cid1, payload)
    print(f"  HTTP Status: {status1}")
    print(f"  Response OK: {body1.get('ok')}")
    
    # Check logs immediately with retry logic
    found_cid1, cid1_messages, attempts1, events_checked1 = check_correlation_id_in_logs(
        log_group_name, cid1, test1_start
    )
    
    print(f"\n  CHECK: correlation_id in grep-friendly logs:")
    print(f"    Pattern: correlation_id={cid1}")
    print(f"    Found: {found_cid1}")
    print(f"    Attempts made: {attempts1}")
    print(f"    Events checked: {events_checked1}")
    if cid1_messages:
        print(f"    Sample matched log line: {cid1_messages[0][:120]}...")
    
    # Test 2: Error request with correlation ID
    print("\n" + "-" * 60)
    print("TEST 2: Error Request with Correlation ID")
    print("-" * 60)
    
    cid2 = generate_correlation_id("obs-err")
    print(f"  Correlation ID: {cid2}")
    
    test2_start = datetime.now(timezone.utc)
    
    # Force an error by sending invalid JSON
    status2, body2 = force_error_request(url, cid2, error_type="invalid_json")
    print(f"  HTTP Status: {status2}")
    print(f"  Response: {body2}")
    
    # Check error correlation ID in logs with retry logic
    found_cid2, cid2_messages, attempts2, events_checked2 = check_correlation_id_in_logs(
        log_group_name, cid2, test2_start
    )
    
    # Check if it's an error (400 for client error, 500 for server error)
    is_client_error = 400 <= status2 < 500
    is_server_error = status2 >= 500
    error_type_str = "ClientErrors" if is_client_error else ("ServerErrors" if is_server_error else "Unknown")
    
    print(f"\n  CHECK: correlation_id in error logs:")
    print(f"    Pattern: correlation_id={cid2}")
    print(f"    Found: {found_cid2}")
    print(f"    Attempts made: {attempts2}")
    print(f"    Events checked: {events_checked2}")
    if cid2_messages:
        print(f"    Sample matched log line: {cid2_messages[0][:120]}...")
    print(f"    HTTP Status: {status2} -> {error_type_str}")
    
    # Test 3: EMF Metrics
    print("\n" + "-" * 60)
    print("TEST 3: EMF Metrics Validation")
    print("-" * 60)
    
    # Query logs for EMF entries (use a broader time range)
    emf_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    emf_results, emf_entries = check_emf_in_logs(log_group_name, emf_start)
    
    print(f"  CHECK: EMF metrics present:")
    print(f"    Requests: {emf_results['Requests']} {'✅' if emf_results['Requests'] else '❌'}")
    print(f"    LatencyMs: {emf_results['LatencyMs']} {'✅' if emf_results['LatencyMs'] else '❌'}")
    print(f"    ClientErrors: {emf_results['ClientErrors']} {'✅' if emf_results['ClientErrors'] else '❌'}")
    print(f"    ServerErrors: {emf_results['ServerErrors']} {'✅' if emf_results['ServerErrors'] else '❌'}")
    
    # Show sample EMF entry
    if emf_entries:
        print(f"\n  Sample EMF entry:")
        sample = emf_entries[0]
        print(f"    Requests: {sample.get('Requests')}")
        print(f"    LatencyMs: {sample.get('LatencyMs')}")
        print(f"    ClientErrors: {sample.get('ClientErrors')}")
        print(f"    ServerErrors: {sample.get('ServerErrors')}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    results = {
        "logs_contain_cid": found_cid1,
        "logs_contain_cid2_error": found_cid2,
        "emf_requests": emf_results["Requests"],
        "emf_latency": emf_results["LatencyMs"],
        "emf_error_counter": emf_results["ClientErrors"] or emf_results["ServerErrors"],
    }
    
    print(f"\n  ✅/❌ Checklist:")
    print(f"    - logs contain CID:       {'✅' if results['logs_contain_cid'] else '❌'}")
    print(f"    - logs contain CID2 error: {'✅' if results['logs_contain_cid2_error'] else '❌'}")
    print(f"    - EMF Requests present:    {'✅' if results['emf_requests'] else '❌'}")
    print(f"    - EMF LatencyMs present:  {'✅' if results['emf_latency'] else '❌'}")
    print(f"    - EMF error counter:      {'✅' if results['emf_error_counter'] else '❌'}")
    
    # Document error classification
    print(f"\n  Error Classification (per handler code):")
    print(f"    - ClientErrors: 400 <= http_status < 500 (client-side errors)")
    print(f"    - ServerErrors: http_status >= 500 (server-side errors)")
    print(f"    - Test 2 triggered: {error_type_str} (HTTP {status2})")
    
    all_passed = all(results.values())
    
    print(f"\n{'='*60}")
    if all_passed:
        print("FINAL RESULT: PASS ✅")
    else:
        print("FINAL RESULT: FAIL ❌")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
