"""Learning scaffold package for trajectory-based learning inputs.

This module provides infrastructure for converting validated experiment trajectories
into learning-ready datasets. This is NOT RL training - it's a deterministic
scaffold that proves the architecture can close the loop from experiments to learning.

Key components:
- selector: Select structurally valid runs for learning
- dataset_export: Convert trajectories to JSONL learning datasets
- replay: Iterate over exported trajectory datasets
- stub_learner: Compute aggregate statistics from trajectories
"""

from .dataset_export import export_learning_dataset
from .replay import iter_trajectory_steps, load_learning_dataset
from .selector import select_learning_runs
from .stub_learner import run_stub_learner

__all__ = [
    "export_learning_dataset",
    "iter_trajectory_steps",
    "load_learning_dataset",
    "select_learning_runs",
    "run_stub_learner",
]
