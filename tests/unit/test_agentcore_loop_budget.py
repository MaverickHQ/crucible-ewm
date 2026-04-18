from services.core.agentcore_loop.run import run_agentcore_loop
from services.core.agentcore_loop.types import LoopBudgets, LoopRequest


def test_loop_rejects_nonzero_model_budget() -> None:
    req = LoopRequest(budgets=LoopBudgets(max_model_calls=1))
    out = run_agentcore_loop(req)
    assert out["ok"] is False
    assert out["error"]["code"] == "invalid_budget"


def test_loop_enforces_max_steps_budget() -> None:
    """
    Test that runtime_budgets.max_steps is enforced.
    
    When budgets.max_steps is less than request.steps, the execution
    should be limited to budgets.max_steps.
    """
    req = LoopRequest(
        budgets=LoopBudgets(max_steps=2),
        steps=5,  # Request 5 steps but budget limits to 2
        seed=42,
        symbols=("AAPL",),
        write_artifacts=False,
        upload_s3=False,
    )
    out = run_agentcore_loop(req)
    assert out["ok"] is True
    # Steps should be limited to max_steps (2), not requested steps (5)
    assert out["steps"] == 2, f"Expected steps=2 (budget enforced), got {out['steps']}"


def test_loop_enforces_max_steps_with_dict_budgets() -> None:
    """
    Test that runtime_budgets.max_steps works with dict-style budgets (JSON input).
    """
    req = LoopRequest(
        budgets={"max_steps": 3, "max_tool_calls": 10},  # Dict-style budgets
        steps=7,  # Request 7 steps but budget limits to 3
        seed=42,
        symbols=("MSFT",),
        write_artifacts=False,
        upload_s3=False,
    )
    out = run_agentcore_loop(req)
    assert out["ok"] is True
    # Steps should be limited to max_steps (3), not requested steps (7)
    assert out["steps"] == 3, f"Expected steps=3 (budget enforced), got {out['steps']}"
