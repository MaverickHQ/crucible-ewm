"""
Environment Package

A minimal trading environment abstraction layer for deterministic, stateful
agent experiments.

This package provides:
- BaseEnvironment: Abstract interface for stateful environments
- TradingEnvironment: Deterministic market path replay environment
- MarketPathEnvironment: Alias for TradingEnvironment

These are lightweight abstractions designed to support future environment-based
work (e.g., Essay 8 "Agents Need Worlds") without introducing RL training,
broker simulation, or world model implementations.
"""

from .base_env import BaseEnvironment
from .trading_env import MarketPathEnvironment, TradingEnvironment

__all__ = [
    "BaseEnvironment",
    "TradingEnvironment",
    "MarketPathEnvironment",
]
