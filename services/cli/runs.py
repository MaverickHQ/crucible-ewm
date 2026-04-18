from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from services.cli.check import _detect_repo_root


def _repo_root(cwd: Path | None = None) -> Path | None:
    return _detect_repo_root(cwd or Path.cwd())


def _candidate_paths(root: Path) -> list[Path]:
    return [
        root / "tmp" / "demo_local_loop" / "runs.json",
        root / "tmp" / "demo_local_loop" / "state.json",
    ]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _looks_like_run(d: Any) -> bool:
    """
    Strict run-object detection:

    Accept if:
      - has run_id (string)  OR
      - has approved (bool) AND steps is a list

    This avoids false positives from arbitrary dicts that happen to have "approved".
    """
    if not isinstance(d, dict):
        return False

    run_id = d.get("run_id")
    if isinstance(run_id, str) and run_id:
        return True

    approved = d.get("approved")
    steps = d.get("steps")
    if isinstance(approved, bool) and isinstance(steps, list):
        return True

    return False


def _parse_ts(v: Any) -> datetime | None:
    """Parse ISO timestamp string to datetime. Accepts 'Z' suffix."""
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def _pick_latest(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the latest run by created_at timestamp, else fallback to last element."""
    if not runs:
        return None

    ts_valid: list[tuple[dict[str, Any], datetime]] = []
    for r in runs:
        ts = _parse_ts(r.get("created_at"))
        if ts is not None:
            ts_valid.append((r, ts))

    if ts_valid:
        return max(ts_valid, key=lambda x: x[1])[0]

    return runs[-1]


def _extract_runs(obj: Any) -> list[dict[str, Any]]:
    """
    Extract runs from multiple formats:
      - [run, run, ...]
      - {"runs": [run, ...]}
      - {run_id: run, run_id2: run2, ...}
      - single run object
    """
    if isinstance(obj, list):
        return [item for item in obj if _looks_like_run(item)]

    if isinstance(obj, dict):
        runs_val = obj.get("runs")
        if isinstance(runs_val, list):
            return [item for item in runs_val if _looks_like_run(item)]

        # dict-of-runs: {uuid: run_obj, ...}
        if obj:
            values = list(obj.values())
            if values and all(_looks_like_run(v) for v in values):
                # Keep stable order when possible
                # (JSON object order is preserved in Python 3.7+)
                return [v for v in values if isinstance(v, dict)]

        if _looks_like_run(obj):
            return [obj]

    return []


def _find_latest_runs_source(root: Path) -> tuple[list[dict[str, Any]], Path | None]:
    for path in _candidate_paths(root):
        if path.exists():
            runs = _extract_runs(_read_json(path))
            if runs:
                return runs, path

    artifacts = root / "tmp" / "demo_local_loop" / "artifacts"
    if artifacts.exists():
        executions = sorted(artifacts.rglob("executions.json"))
        if executions:
            latest = executions[-1]
            rows = _extract_runs(_read_json(latest))
            if rows:
                return rows, latest

    return [], None


def _format_rejection_error(err: Any) -> str:
    """
    Convert structured errors into readable single-line text.
    Handles:
      - dict: {"code": "...", "message": "..."}
      - str: "..."
      - anything else: str(err)
    """
    if isinstance(err, dict):
        code = err.get("code")
        msg = err.get("message") or err.get("detail") or err.get("error")
        if code and msg:
            return f"{code} - {msg}"
        if code:
            return str(code)
        if msg:
            return str(msg)
        return str(err)
    if isinstance(err, str):
        return err
    return str(err)


def _latest_summary_lines(run: dict[str, Any]) -> list[str]:
    run_id = run.get("run_id", "unknown")
    approved = run.get("approved")
    steps = run.get("steps")
    step_count = len(steps) if isinstance(steps, list) else 0

    created_at = run.get("created_at")
    created_at_str = created_at if isinstance(created_at, str) and created_at.strip() else None

    trajectory = run.get("trajectory")
    final_state: dict[str, Any] = {}
    if isinstance(trajectory, list) and trajectory and isinstance(trajectory[-1], dict):
        final_state = trajectory[-1]

    decision = "APPROVED" if approved is True else ("REJECTED" if approved is False else "UNKNOWN")

    lines = [
        f"run_id: {run_id}",
        f"decision: {decision}",
        f"approved: {approved}",
        f"steps: {step_count}",
    ]
    if created_at_str:
        lines.append(f"created_at: {created_at_str}")

    if "cash_balance" in final_state:
        cash = final_state.get("cash_balance")
        if isinstance(cash, (int, float)):
            lines.append(f"final_cash: {cash:.2f}")
        else:
            lines.append(f"final_cash: {cash}")
    if "exposure" in final_state:
        exp = final_state.get("exposure")
        if isinstance(exp, (int, float)):
            lines.append(f"final_exposure: {exp:.2f}")
        else:
            lines.append(f"final_exposure: {exp}")

    positions = final_state.get("positions")
    if isinstance(positions, dict) and positions:
        pos_str = ", ".join(f"{k}={v}" for k, v in positions.items())
        lines.append(f"positions: {pos_str}")
    else:
        lines.append("positions: none")

    plan = run.get("plan")
    if isinstance(plan, dict):
        plan_steps = plan.get("steps")
        if isinstance(plan_steps, list):
            lines.append(f"plan: present ({len(plan_steps)} steps)")
        else:
            lines.append("plan: present")
    else:
        lines.append("plan: none (no planner output recorded)")

    # Rejection details when approved is False
    if approved is False:
        rejected_step_index = run.get("rejected_step_index")
        lines.append(f"rejected_step_index: {rejected_step_index}")

        rejected_step: dict[str, Any] | None = None

        # Prefer explicit rejected_step_index when it points to a step
        if isinstance(rejected_step_index, int) and isinstance(steps, list):
            idx = rejected_step_index
            if 0 <= idx < len(steps) and isinstance(steps[idx], dict):
                rejected_step = steps[idx]

        # Fallback: first step with accepted == False
        if rejected_step is None and isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and step.get("accepted") is False:
                    rejected_step = step
                    break

        if rejected_step:
            action = rejected_step.get("action", {})
            if isinstance(action, dict):
                action_type = action.get("type") or action.get("action_type") or "unknown"
                symbol = action.get("symbol") or ""
                quantity = action.get("quantity")
                price = action.get("price")
                lines.append(f"rejected_action: {action_type} {symbol} {quantity}@{price}")

            errors = rejected_step.get("errors")
            if errors is None:
                errors = rejected_step.get("error")

            # Normalize errors into a short readable list
            if isinstance(errors, list) and errors:
                formatted = [_format_rejection_error(e) for e in errors[:3]]
                lines.append(f"rejected_errors: {'; '.join(formatted)}")
            elif isinstance(errors, dict):
                lines.append(f"rejected_errors: {_format_rejection_error(errors)}")
            elif isinstance(errors, str) and errors.strip():
                lines.append(f"rejected_errors: {errors.strip()[:200]}")

    return lines


def runs_latest(cwd: Path | None = None, *, raw: bool = False, json_output: bool = False) -> int:
    root = _repo_root(cwd)
    if root is None:
        print("No local runs found. Run scripts/demo_local_loop.py first.")
        return 0

    runs, source = _find_latest_runs_source(root)
    if not runs:
        print("No local runs found. Run scripts/demo_local_loop.py first.")
        return 0

    latest = _pick_latest(runs)
    if latest is None:
        print("No local runs found. Run scripts/demo_local_loop.py first.")
        return 0

    if raw:
        print(json.dumps(latest, default=str))
        return 0

    if json_output:
        print(json.dumps(latest, indent=2, sort_keys=True, default=str))
        return 0

    print(f"source: {source}")
    for line in _latest_summary_lines(latest):
        print(line)
    return 0


def runs_tail(n: int, cwd: Path | None = None) -> int:
    root = _repo_root(cwd)
    if root is None:
        print("No local runs found. Run scripts/demo_local_loop.py first.")
        return 0

    runs, source = _find_latest_runs_source(root)
    if not runs:
        print("No local runs found. Run scripts/demo_local_loop.py first.")
        return 0

    tail = runs[-max(1, n) :]
    print(f"source: {source}")
    print(json.dumps(tail, indent=2, sort_keys=True, default=str))
    return 0
