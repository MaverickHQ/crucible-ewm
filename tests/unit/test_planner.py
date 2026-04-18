from pathlib import Path

from services.core.market import MarketPath
from services.core.planner import MockPlanner, run_planned_simulation
from services.core.policy.versioning import ensure_policy_metadata
from services.core.state import RiskLimits, State


def _base_state():
    return State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )


def test_mock_planner_returns_plan():
    planner = MockPlanner()
    result = planner.propose({}, {}, "approve")

    assert result.planner_name == "mock"
    assert result.plan


def test_run_planned_simulation_rejects_with_rejection_info():
    planner = MockPlanner()
    policy = ensure_policy_metadata({"policy_id": "default"})
    market_path = MarketPath.from_fixture(Path("examples/fixtures/trading_path.json"))

    planner_result, simulation = run_planned_simulation(
        planner=planner,
        initial_state=_base_state(),
        market_path=market_path,
        policy=policy,
        goal="reject",
        state_summary=_base_state().to_dict(),
    )

    assert not simulation.approved
    assert planner_result.rejection is not None
    assert planner_result.rejection.rejected_step_index == simulation.rejected_step_index
    assert planner_result.rejection.violations
