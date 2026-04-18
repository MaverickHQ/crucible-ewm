from __future__ import annotations

from ewm_core.agentcore_loop.run import run_agentcore_loop
from ewm_core.agentcore_loop.types import LoopBudgets, LoopRequest


def test_planner_disabled_returns_no_plan(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LOCAL_PLANNER", "0")
    req = LoopRequest(budgets=LoopBudgets(max_model_calls=0))
    out = run_agentcore_loop(req)
    assert out["ok"] is True
    assert out.get("plan") is None


def test_planner_enabled_returns_plan(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LOCAL_PLANNER", "1")
    req = LoopRequest(budgets=LoopBudgets(max_model_calls=0))
    out = run_agentcore_loop(req)
    assert out["ok"] is True
    plan = out.get("plan")
    assert plan is not None
    assert plan["meta"]["planner"] == "local"
    assert len(plan["steps"]) >= 3
    assert plan["steps"][0]["tool"] == "validate_request"
