#!/usr/bin/env python3
"""
Script to generate publication-ready charts from experiment evaluation outputs.

Reads evaluation_summary.json and evaluation_runs.csv from an experiment directory
and generates PNG images for Essay 7 / Substack.

Usage:
    python3 scripts/plot_experiment.py --experiment-dir <path>
    
Optional:
    --style default
    --dpi 180
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Use matplotlib - check if available
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    print("ERROR: matplotlib is required. Install with: pip install matplotlib")
    sys.exit(1)


# =============================================================================
# CONSTANTS
# =============================================================================

OUTPUT_FILES = [
    "termination_modes_bar.png",
    "integrity_rate_bar.png",
    "run_length_histogram.png",
    "experiment_stability_table.png",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_experiment_inputs(experiment_dir: Path) -> tuple[dict, list[dict]]:
    """
    Load evaluation_summary.json and evaluation_runs.csv from experiment directory.
    
    Args:
        experiment_dir: Path to the experiment directory.
        
    Returns:
        Tuple of (evaluation_summary dict, runs list from CSV).
        
    Raises:
        FileNotFoundError: If required files are missing.
        ValueError: If file format is invalid.
    """
    experiment_dir = Path(experiment_dir)
    
    # Load JSON summary
    json_path = experiment_dir / "evaluation_summary.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"evaluation_summary.json not found in {experiment_dir}. "
            "Please run evaluation first."
        )
    
    with open(json_path, 'r', encoding='utf-8') as f:
        evaluation_summary = json.load(f)
    
    # Load CSV runs data
    csv_path = experiment_dir / "evaluation_runs.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"evaluation_runs.csv not found in {experiment_dir}. "
            "Please run evaluation first."
        )
    
    runs = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse integrity_errors - could be semicolon-separated string or empty
            integrity_errors = row.get('integrity_errors', '')
            if integrity_errors:
                integrity_errors_list = integrity_errors.split(';')
            else:
                integrity_errors_list = []
            
            # Parse manifest_valid
            manifest_valid = row.get('manifest_valid', '')
            if manifest_valid.lower() == 'true':
                manifest_valid = True
            elif manifest_valid.lower() == 'false':
                manifest_valid = False
            else:
                manifest_valid = None
            
            # Parse steps_executed
            steps_executed = row.get('steps_executed', '')
            if steps_executed:
                try:
                    steps_executed = int(steps_executed)
                except ValueError:
                    steps_executed = None
            else:
                steps_executed = None
            
            # Parse truncated_by_budget
            truncated_by_budget = row.get('truncated_by_budget', '')
            if truncated_by_budget.lower() == 'true':
                truncated_by_budget = True
            elif truncated_by_budget.lower() == 'false':
                truncated_by_budget = False
            else:
                truncated_by_budget = None
            
            runs.append({
                'run_id': row.get('run_id', ''),
                'manifest_valid': manifest_valid,
                'integrity_errors': integrity_errors_list,
                'steps_executed': steps_executed,
                'truncated_by_budget': truncated_by_budget,
            })
    
    return evaluation_summary, runs


def classify_runs(runs: list[dict]) -> dict[str, int]:
    """
    Classify runs into termination categories.
    
    Categories:
    - "integrity failure": integrity_errors is not empty
    - "structural truncation": truncated_by_budget == true (and no integrity errors)
    - "natural completion": otherwise (completed without truncation)
    
    Args:
        runs: List of run dictionaries with integrity_errors, truncated_by_budget fields.
        
    Returns:
        Dictionary mapping category to count.
    """
    categories = {
        "integrity failure": 0,
        "structural truncation": 0,
        "natural completion": 0,
    }
    
    for run in runs:
        integrity_errors = run.get('integrity_errors', [])
        truncated_by_budget = run.get('truncated_by_budget')
        
        # Check integrity errors first
        if integrity_errors:
            categories["integrity failure"] += 1
        # Check truncation
        elif truncated_by_budget is True:
            categories["structural truncation"] += 1
        # Natural completion
        else:
            categories["natural completion"] += 1
    
    return categories


def plot_termination_modes(categories: dict[str, int], output_path: Path, dpi: int = 180) -> None:
    """
    Generate bar chart for run termination modes.
    
    Args:
        categories: Dictionary of category -> count.
        output_path: Path to save the PNG file.
        dpi: Resolution for the output image.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Sort categories for consistent ordering
    category_order = ["natural completion", "structural truncation", "integrity failure"]
    labels = category_order
    values = [categories.get(cat, 0) for cat in category_order]
    
    # Create bars with consistent colors
    colors = ['#4CAF50', '#FF9800', '#F44336']  # Green, Orange, Red
    
    bars = ax.bar(labels, values, color=colors, edgecolor='black', linewidth=0.5)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(
                f'{int(height)}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=11,
                fontweight='bold',
            )
    
    ax.set_title("Run Termination Modes", fontsize=14, fontweight='bold', pad=10)
    ax.set_ylabel("Runs", fontsize=12)
    ax.set_xlabel("")
    
    # Rotate x-tick labels slightly for readability
    plt.xticks(rotation=15, ha='right')
    
    # Add grid for readability
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)


def plot_integrity_rate(runs: list[dict], output_path: Path, dpi: int = 180) -> None:
    """
    Generate horizontal bar chart for structural integrity rate.
    
    Args:
        runs: List of run dictionaries.
        output_path: Path to save the PNG file.
        dpi: Resolution for the output image.
    """
    # Classify runs
    valid_runs = 0
    integrity_failures = 0
    
    for run in runs:
        manifest_valid = run.get('manifest_valid')
        integrity_errors = run.get('integrity_errors', [])
        
        # Valid run = manifest_valid == True AND no integrity errors
        if manifest_valid is True and not integrity_errors:
            valid_runs += 1
        elif integrity_errors:
            integrity_failures += 1
    
    categories = ["Structurally valid", "Integrity failure"]
    values = [valid_runs, integrity_failures]
    
    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(8, 4))
    
    colors = ['#4CAF50', '#F44336']  # Green for valid, Red for failures
    y_pos = range(len(categories))
    
    bars = ax.barh(y_pos, values, color=colors, edgecolor='black', linewidth=0.5, height=0.6)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, values)):
        ax.annotate(
            f'{val}',
            xy=(val, bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0),  # 5 points horizontal offset
            textcoords="offset points",
            ha='left', va='center',
            fontsize=12,
            fontweight='bold',
        )
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=11)
    ax.set_xlabel("Runs", fontsize=12)
    ax.set_title("Structural Integrity Rate", fontsize=14, fontweight='bold', pad=10)
    
    # Add grid for readability
    ax.xaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    # Set x-axis to start at 0
    ax.set_xlim(left=0)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)


def plot_run_length_histogram(runs: list[dict], output_path: Path, dpi: int = 180) -> None:
    """
    Generate histogram for execution length distribution.
    
    Args:
        runs: List of run dictionaries.
        output_path: Path to save the PNG file.
        dpi: Resolution for the output image.
    """
    # Extract non-null steps_executed
    steps_values = [
        run['steps_executed'] 
        for run in runs 
        if run.get('steps_executed') is not None
    ]
    
    if not steps_values:
        steps_values = [0]
    
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Create histogram
    n, bins, patches = ax.hist(
        steps_values, 
        bins='auto', 
        color='#2196F3',  # Blue
        edgecolor='black', 
        linewidth=0.5,
        alpha=0.8,
    )
    
    # Add value labels on bars
    for patch, count in zip(patches, n):
        if count > 0:
            ax.annotate(
                f'{int(count)}',
                xy=(patch.get_x() + patch.get_width() / 2, count),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=10,
                fontweight='bold',
            )
    
    ax.set_title("Execution Length Distribution", fontsize=14, fontweight='bold', pad=10)
    ax.set_xlabel("Steps executed", fontsize=12)
    ax.set_ylabel("Runs", fontsize=12)
    
    # Add grid for readability
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)


def render_stability_table(evaluation_summary: dict, runs: list[dict], output_path: Path, dpi: int = 180) -> None:
    """
    Render a styled table as PNG for experiment stability summary.
    
    Args:
        evaluation_summary: The evaluation summary dictionary.
        runs: List of run dictionaries.
        output_path: Path to save the PNG file.
        dpi: Resolution for the output image.
    """
    # Calculate metrics
    total_runs = len(runs)
    
    valid_runs = 0
    integrity_failures = 0
    steps_list = []
    truncated_count = 0
    
    for run in runs:
        manifest_valid = run.get('manifest_valid')
        integrity_errors = run.get('integrity_errors', [])
        steps_executed = run.get('steps_executed')
        truncated_by_budget = run.get('truncated_by_budget')
        
        if manifest_valid is True and not integrity_errors:
            valid_runs += 1
        
        if integrity_errors:
            integrity_failures += 1
        
        if steps_executed is not None:
            steps_list.append(steps_executed)
        
        if truncated_by_budget is True:
            truncated_count += 1
    
    avg_steps = sum(steps_list) / len(steps_list) if steps_list else 0
    pct_truncated = (truncated_count / total_runs * 100) if total_runs > 0 else 0
    
    # Prepare table data
    table_data = [
        ["Total runs", str(total_runs)],
        ["Structurally valid runs", str(valid_runs)],
        ["Integrity failures", str(integrity_failures)],
        ["Avg steps executed", f"{avg_steps:.1f}"],
        ["Pct truncated by budget", f"{pct_truncated:.1f}%"],
    ]
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('off')
    
    # Title above table
    fig.suptitle("Experiment Stability Summary", fontsize=16, fontweight='bold', y=0.95)
    
    # Create table
    table = ax.table(
        cellText=table_data,
        colLabels=["Metric", "Value"],
        colWidths=[0.5, 0.3],
        cellLoc='left',
        loc='center',
        bbox=[0.2, 0.1, 0.6, 0.8],
    )
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Style header row
    for i in range(2):
        cell = table[(0, i)]
        cell.set_facecolor('#E0E0E0')
        cell.set_text_props(fontweight='bold')
        cell.set_edgecolor('black')
    
    # Style data rows
    for row in range(1, len(table_data) + 1):
        for col in range(2):
            cell = table[(row, col)]
            cell.set_edgecolor('black')
            if col == 1:  # Value column
                cell.set_text_props(fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate publication-ready charts from experiment evaluation outputs."
    )
    parser.add_argument(
        "--experiment-dir",
        type=str,
        required=True,
        help="Path to the experiment directory containing evaluation_summary.json and evaluation_runs.csv",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="default",
        choices=["default"],
        help="Style preset (default)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=180,
        help="Resolution for output images (default: 180)",
    )
    
    args = parser.parse_args()
    
    experiment_dir = Path(args.experiment_dir)
    
    # Validate experiment directory exists
    if not experiment_dir.exists():
        print(f"ERROR: Experiment directory does not exist: {experiment_dir}", file=sys.stderr)
        return 2
    
    if not experiment_dir.is_dir():
        print(f"ERROR: Path is not a directory: {experiment_dir}", file=sys.stderr)
        return 2
    
    # Validate required files exist
    json_path = experiment_dir / "evaluation_summary.json"
    csv_path = experiment_dir / "evaluation_runs.csv"
    
    if not json_path.exists():
        print(f"ERROR: evaluation_summary.json not found in {experiment_dir}", file=sys.stderr)
        print("Please run evaluation first to generate the required files.", file=sys.stderr)
        return 2
    
    if not csv_path.exists():
        print(f"ERROR: evaluation_runs.csv not found in {experiment_dir}", file=sys.stderr)
        print("Please run evaluation first to generate the required files.", file=sys.stderr)
        return 2
    
    # Load experiment data
    try:
        evaluation_summary, runs = load_experiment_inputs(experiment_dir)
    except Exception as e:
        print(f"ERROR: Failed to load experiment data: {e}", file=sys.stderr)
        return 1
    
    # Create figures directory
    figures_dir = experiment_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate charts
    dpi = args.dpi
    
    # 1) termination_modes_bar.png
    categories = classify_runs(runs)
    termination_path = figures_dir / "termination_modes_bar.png"
    plot_termination_modes(categories, termination_path, dpi)
    
    # 2) integrity_rate_bar.png
    integrity_path = figures_dir / "integrity_rate_bar.png"
    plot_integrity_rate(runs, integrity_path, dpi)
    
    # 3) run_length_histogram.png
    histogram_path = figures_dir / "run_length_histogram.png"
    plot_run_length_histogram(runs, histogram_path, dpi)
    
    # 4) experiment_stability_table.png
    table_path = figures_dir / "experiment_stability_table.png"
    render_stability_table(evaluation_summary, runs, table_path, dpi)
    
    # Print summary
    print(f"Generated {len(OUTPUT_FILES)} figures in {figures_dir}:")
    for filename in OUTPUT_FILES:
        filepath = figures_dir / filename
        if filepath.exists():
            size_kb = filepath.stat().st_size / 1024
            print(f"  - {filename} ({size_kb:.1f} KB)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
