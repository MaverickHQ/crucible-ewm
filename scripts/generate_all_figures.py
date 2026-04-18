#!/usr/bin/env python3
"""
Generate all publication-quality diagrams for the essay series.

This script runs all three diagram generators and outputs SVG and PNG files
to the docs/figures directory.
"""

import os
import sys

# Add the scripts directory to the path so we can import the generators
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagrams.generate_agent_stack_diagram import create_agent_stack_diagram
from diagrams.generate_tools_vs_environment_diagram import create_tools_vs_environment_diagram
from diagrams.generate_agent_experiment_diagram import create_agent_experiment_diagram


def main():
    """Generate all figures."""
    print("=" * 60)
    print("Generating publication-quality diagrams for essay series")
    print("=" * 60)
    print()
    
    # Ensure output directory exists
    os.makedirs("docs/figures", exist_ok=True)
    
    # Generate all diagrams
    print("Generating Agent Stack diagram...")
    create_agent_stack_diagram()
    print()
    
    print("Generating Tools vs Environment diagram...")
    create_tools_vs_environment_diagram()
    print()
    
    print("Generating Agent Experiment Trajectory diagram...")
    create_agent_experiment_diagram()
    print()
    
    print("=" * 60)
    print("Generated:")
    print("  docs/figures/agent_stack.svg")
    print("  docs/figures/agent_stack.png")
    print("  docs/figures/tools_vs_environment.svg")
    print("  docs/figures/tools_vs_environment.png")
    print("  docs/figures/agent_experiment_trajectory.svg")
    print("  docs/figures/agent_experiment_trajectory.png")
    print("=" * 60)


if __name__ == "__main__":
    main()
