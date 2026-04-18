from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, List

from ewm_core.actions.types import PlaceBuy, PlaceSell
from ewm_core.market import MarketPath
from ewm_core.state.models import State
from ewm_core.strategy.types import (
    MeanReversionRule,
    Signal,
    SmaCrossoverRule,
    StrategySpec,
    ThresholdPriceRule,
)


@dataclass(frozen=True)
class StrategyEvaluation:
    signals: Dict[str, Signal]
    rationales: Dict[str, str]


def _prices_for_symbol(path: MarketPath, symbol: str, step_index: int) -> List[float]:
    if step_index < 0:
        return []
    return [step.get(symbol) for step in path.steps[: step_index + 1] if symbol in step]


def _threshold_signal(rule: ThresholdPriceRule, price: float) -> tuple[Signal, str]:
    if rule.buy_below is not None and price <= rule.buy_below:
        return (
            Signal.BUY,
            f"price < buy_below ({price:.2f} < {rule.buy_below:.2f})",
        )
    if rule.sell_above is not None and price >= rule.sell_above:
        return (
            Signal.SELL,
            f"price > sell_above ({price:.2f} > {rule.sell_above:.2f})",
        )
    return Signal.HOLD, "price within thresholds"


def _sma_signal(rule: SmaCrossoverRule, history: List[float]) -> tuple[Signal, str]:
    if len(history) < rule.long_window:
        return Signal.HOLD, "insufficient history for SMA"
    short_window = history[-rule.short_window :]
    long_window = history[-rule.long_window :]
    short_sma = mean(short_window)
    long_sma = mean(long_window)
    if short_sma > long_sma:
        return (
            Signal.BUY,
            f"SMA(short)={short_sma:.2f} > SMA(long)={long_sma:.2f}",
        )
    if short_sma < long_sma:
        return (
            Signal.SELL,
            f"SMA(short)={short_sma:.2f} < SMA(long)={long_sma:.2f}",
        )
    return Signal.HOLD, f"SMA(short)={short_sma:.2f} == SMA(long)={long_sma:.2f}"


def _zscore_signal(
    rule: MeanReversionRule,
    history: List[float],
    price: float,
) -> tuple[Signal, str]:
    if len(history) < rule.window:
        return Signal.HOLD, "insufficient history for z-score"
    window = history[-rule.window :]
    window_mean = mean(window)
    window_std = pstdev(window)
    if window_std == 0:
        return Signal.HOLD, "z-score undefined (std=0)"
    zscore = (price - window_mean) / window_std
    if zscore <= rule.z_buy_below:
        return (
            Signal.BUY,
            f"z-score={zscore:.2f} < {rule.z_buy_below:.2f}",
        )
    if zscore >= rule.z_sell_above:
        return (
            Signal.SELL,
            f"z-score={zscore:.2f} > {rule.z_sell_above:.2f}",
        )
    return Signal.HOLD, f"z-score={zscore:.2f} within bands"


def evaluate_signals(
    strategy: StrategySpec,
    state: State,
    price_ctx: Dict[str, float],
    step_index: int,
    market_path: MarketPath | None = None,
) -> Dict[str, Signal]:
    evaluation = evaluate_signals_with_rationale(
        strategy=strategy,
        state=state,
        price_ctx=price_ctx,
        step_index=step_index,
        market_path=market_path,
    )
    return evaluation.signals


def evaluate_signals_with_rationale(
    strategy: StrategySpec,
    state: State,
    price_ctx: Dict[str, float],
    step_index: int,
    market_path: MarketPath | None = None,
) -> StrategyEvaluation:
    signals = {symbol: Signal.HOLD for symbol in strategy.universe.symbols}
    rationales = {symbol: "" for symbol in strategy.universe.symbols}

    for rule in strategy.rules:
        symbol = rule.symbol
        price = price_ctx.get(symbol)
        if price is None:
            continue

        if isinstance(rule, ThresholdPriceRule):
            signal, rationale = _threshold_signal(rule, price)
        elif isinstance(rule, SmaCrossoverRule):
            history = (
                _prices_for_symbol(market_path, symbol, step_index)
                if market_path is not None
                else []
            )
            signal, rationale = _sma_signal(rule, history)
        elif isinstance(rule, MeanReversionRule):
            history = (
                _prices_for_symbol(market_path, symbol, step_index)
                if market_path is not None
                else []
            )
            signal, rationale = _zscore_signal(rule, history, price)
        else:
            signal, rationale = Signal.HOLD, "no matching rule"

        if signal != Signal.HOLD:
            signals[symbol] = signal
            rationales[symbol] = rationale

        if signal == Signal.HOLD and not rationales.get(symbol):
            rationales[symbol] = rationale

    return StrategyEvaluation(signals=signals, rationales=rationales)


def signals_to_actions(
    strategy: StrategySpec,
    state: State,
    price_ctx: Dict[str, float],
    signals: Dict[str, Signal],
) -> list:
    actions = []
    order_qty = float(strategy.sizing.order_qty)
    max_qty = float(strategy.sizing.max_position_qty_per_symbol)
    max_exposure = strategy.sizing.max_new_exposure_per_step
    exposure_used = 0.0

    for symbol in strategy.universe.symbols:
        signal = signals.get(symbol, Signal.HOLD)
        price = price_ctx.get(symbol)
        if price is None:
            continue

        if signal == Signal.BUY:
            current_qty = state.positions.get(symbol, 0.0)
            if current_qty + order_qty > max_qty:
                continue
            cost = price * order_qty
            if max_exposure is not None and exposure_used + cost > max_exposure:
                continue
            if state.cash_balance < cost:
                continue
            exposure_used += cost
            actions.append(PlaceBuy(symbol=symbol, quantity=order_qty, price=price))

        elif signal == Signal.SELL:
            current_qty = state.positions.get(symbol, 0.0)
            if current_qty <= 0:
                continue
            sell_qty = min(order_qty, current_qty)
            actions.append(PlaceSell(symbol=symbol, quantity=sell_qty, price=price))

    return actions
