from __future__ import annotations

from dataclasses import replace
from typing import Dict, List

from ewm_core.actions import PlaceBuy
from ewm_core.artifacts import ArtifactWriter, RunContext
from ewm_core.broker import LocalPaperBroker, OrderRequest
from ewm_core.deltas.compute import compute_state_delta
from ewm_core.execution import execute_run
from ewm_core.loop.types import ExecutionBundle, ExecutionRow, LoopResult
from ewm_core.market import MarketPath
from ewm_core.observability import TapeRow
from ewm_core.persistence import PolicyStore, RunStore, StateStore
from ewm_core.simulator import simulate_plan
from ewm_core.state import RiskLimits, State
from ewm_core.strategy import evaluate_signals_with_rationale, signals_to_actions
from ewm_core.transitions import apply_action


def _format_signals(signals: Dict[str, object]) -> Dict[str, str]:
    return {symbol: signal.value for symbol, signal in signals.items()}


def _actions_with_prices(actions: List[object], prices: Dict[str, float]) -> List[object]:
    priced_actions = []
    for action in actions:
        price = prices.get(action.symbol, action.price)
        priced_actions.append(replace(action, price=price))
    return priced_actions


def _positions_slice(state: State, symbols: List[str]) -> Dict[str, float]:
    return {symbol: state.positions.get(symbol, 0.0) for symbol in symbols}


def _extract_symbol_reason(step_reason: str, symbol: str) -> str:
    token = f"{symbol}:"
    if token not in step_reason:
        return step_reason
    start = step_reason.index(token)
    remainder = step_reason[start + len(token) :].lstrip()
    parts = remainder.split(";")
    clause = parts[0].strip()
    if clause:
        return f"{symbol}: {clause}"
    return step_reason


def _execution_rows_for_actions(
    step_index: int,
    run_id: str,
    decision: str,
    actions: List[object],
    prices: Dict[str, float],
    prior_state: State,
    next_state: State,
    reason: str,
    verification: str,
) -> List[ExecutionRow]:
    if decision != "APPROVED":
        return []

    execution_rows: List[ExecutionRow] = []
    rolling_state = prior_state

    for action in actions:
        side = "BUY" if isinstance(action, PlaceBuy) else "SELL"
        symbol = action.symbol
        qty = action.quantity
        price = prices.get(symbol, action.price)
        positions_before = _positions_slice(rolling_state, [symbol])
        cash_before = rolling_state.cash_balance
        exposure_before = rolling_state.exposure_value(prices)
        transition = apply_action(rolling_state, action)
        rolling_state = transition.next_state
        positions_after = _positions_slice(rolling_state, [symbol])
        cash_after = rolling_state.cash_balance
        exposure_after = rolling_state.exposure_value(prices)
        symbol_reason = _extract_symbol_reason(reason, symbol)
        execution_rows.append(
            ExecutionRow(
                step_index=step_index,
                run_id=run_id,
                decision=decision,
                symbol=symbol,
                side=side,
                quantity=qty,
                price=price,
                cash_before=cash_before,
                cash_after=cash_after,
                exposure_before=exposure_before,
                exposure_after=exposure_after,
                positions_before=positions_before,
                positions_after=positions_after,
                reason=symbol_reason,
                verification=verification,
            )
        )
    return execution_rows


def run_loop(
    *,
    market_path: MarketPath,
    strategy: object,
    steps: int,
    data_dir: object,
    run_id: str | None = None,
) -> LoopResult:
    data_dir = data_dir
    artifact_dir = data_dir / "artifacts"

    state_store = StateStore(data_dir / "state.json")
    run_store = RunStore(data_dir / "runs.json")
    policy_store = PolicyStore(data_dir / "policies.json")
    artifact_writer = ArtifactWriter(artifact_dir)

    policy = {
        "policy_id": "default",
        "risk_limits": {
            "max_leverage": 2.0,
            "max_position_pct": 0.8,
            "max_position_value": 5_000.0,
        },
    }
    policy_store.save_policy(policy)

    state = State(
        cash_balance=1_000.0,
        positions={},
        exposure=0.0,
        risk_limits=RiskLimits(2.0, 0.8, 5_000.0),
    )
    state_store.init_state(state)

    tape_rows: List[TapeRow] = []
    execution_rows: List[ExecutionRow] = []
    execution_bundles: List[ExecutionBundle] = []
    broker = LocalPaperBroker()

    for step_index in range(steps):
        prices = market_path.price_context(step_index)
        evaluation = evaluate_signals_with_rationale(
            strategy=strategy,
            state=state,
            price_ctx=prices,
            step_index=step_index,
            market_path=market_path,
        )
        signals = _format_signals(evaluation.signals)
        rationales = evaluation.rationales

        actions = signals_to_actions(strategy, state, prices, evaluation.signals)
        action_payloads = [action.to_dict() for action in actions]

        if not actions:
            delta = compute_state_delta(state, state, prices)
            tape_rows.append(
                TapeRow(
                    step_index=step_index,
                    prices=prices,
                    signals=signals,
                    rationales=rationales,
                    actions=action_payloads,
                    decision="HOLD",
                    why="strategy HOLD",
                    explanation="",
                    state_delta=delta,
                    verifier_errors=[],
                    run_id="-",
                    artifact_dir=str(artifact_dir),
                )
            )
            continue

        priced_actions = _actions_with_prices(actions, prices)
        simulation = simulate_plan(
            state,
            priced_actions,
            market_path,
            policy_id=policy["policy_id"],
            policy_version=policy.get("policy_version"),
            policy_hash=policy.get("policy_hash"),
            run_id=run_id,
        )
        run_store.save_run(simulation)

        # Create RunContext with resolved values for manifest
        # Extract symbols from the priced actions
        symbols = sorted(set(action.symbol for action in priced_actions))

        # Resolve policy_limits from policy (trading/risk constraints)
        policy_limits = {
            "max_leverage": policy["risk_limits"]["max_leverage"],
            "max_position_pct": policy["risk_limits"]["max_position_pct"],
            "max_position_value": policy["risk_limits"]["max_position_value"],
        }

        # Runtime budgets come from the loop configuration (passed as parameter or defaults)
        # These are the runtime loop constraints
        runtime_budgets = {
            "max_steps": steps,  # This run's actual step count
            "max_tool_calls": 10,  # Default value
            "max_model_calls": 0,  # Default for loop mode
            "max_memory_ops": 0,
            "max_memory_bytes": 0,
        }

        context = RunContext(
            run_id=simulation.run_id,
            mode="agentcore-loop",
            strategy_path="examples/fixtures/trading_path.json",
            runtime_budgets=runtime_budgets,
            policy_limits=policy_limits,
            symbols=symbols,
        )

        artifacts = artifact_writer.write(simulation, context)

        decision = "APPROVED" if simulation.approved else "REJECTED"
        explanation = simulation.steps[-1].explanation if simulation.steps else ""
        verifier_errors = [
            {"code": error.code, "message": error.message}
            for error in (simulation.steps[-1].errors if simulation.steps else [])
        ]
        if simulation.approved and simulation.trajectory:
            final_state = simulation.trajectory[-1]
            delta = compute_state_delta(state, final_state, prices)
        else:
            final_state = state
            delta = compute_state_delta(state, state, prices)

        why_parts = [
            f"{symbol}: {rationale}"
            for symbol, rationale in rationales.items()
            if signals.get(symbol) != "HOLD"
        ]
        reason = "; ".join(why_parts) if why_parts else "strategy HOLD"
        verification = "verified OK" if simulation.approved else "verification failed"
        why = f"{reason} | {verification}"

        tape_rows.append(
            TapeRow(
                step_index=step_index,
                prices=prices,
                signals=signals,
                rationales=rationales,
                actions=action_payloads,
                decision=decision,
                why=why,
                explanation=explanation,
                state_delta=delta,
                verifier_errors=verifier_errors,
                run_id=simulation.run_id,
                artifact_dir=str(artifacts["decision"]).rsplit("/", 1)[0],
            )
        )

        ledger_rows = _execution_rows_for_actions(
            step_index=step_index,
            run_id=simulation.run_id,
            decision=decision,
            actions=priced_actions,
            prices=prices,
            prior_state=state,
            next_state=final_state,
            reason=reason,
            verification=verification,
        )
        execution_rows.extend(ledger_rows)

        if decision == "APPROVED" and priced_actions:
            orders = [
                OrderRequest(
                    run_id=simulation.run_id,
                    step_index=step_index,
                    action_index=index,
                    symbol=action.symbol,
                    side="BUY" if isinstance(action, PlaceBuy) else "SELL",
                    quantity=action.quantity,
                    limit_price=action.price,
                )
                for index, action in enumerate(priced_actions)
            ]
            events = broker.execute(orders, prices, starting_state=state)
            execution_bundles.append(
                ExecutionBundle(
                    step_index=step_index,
                    run_id=simulation.run_id,
                    artifact_dir=str(artifacts["decision"]).rsplit("/", 1)[0],
                    events=events,
                    ledger_rows=ledger_rows,
                )
            )

        if simulation.approved:
            execution = execute_run(run_store, state_store, simulation.run_id)
            if execution.state is not None:
                state = execution.state

    return LoopResult(
        tape_rows=tape_rows,
        execution_rows=execution_rows,
        execution_bundles=execution_bundles,
        final_state=state,
    )
