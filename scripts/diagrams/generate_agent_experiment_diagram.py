#!/usr/bin/env python3
"""
Generate the Agent Experiment Trajectory diagram.

This script creates a publication-quality flow diagram showing
agent experiments as trajectories through environments.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# Shared styling constants
FONT_FAMILY = "Inter, Helvetica, Arial, sans-serif"
NODE_FILL = "white"
NODE_BORDER = "#444444"
ARROW_COLOR = "#444444"
TEXT_PRIMARY = "#111111"
TEXT_SECONDARY = "#555555"
CANVAS_WIDTH = 10
CANVAS_HEIGHT = 9

# Highlight colors
ARTIFACT_COLOR = "#fff8e1"  # Light yellow
EVALUATION_COLOR = "#e3f2fd"  # Light blue


def draw_box(ax, x, y, width, height, text, color=NODE_FILL, fontsize=12, bold=False):
    """Draw a box with text centered."""
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.1",
        facecolor=color,
        edgecolor=NODE_BORDER,
        linewidth=1.5
    )
    ax.add_patch(box)
    
    weight = 'bold' if bold else 'normal'
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha='center',
        va='center',
        fontsize=fontsize,
        fontfamily=FONT_FAMILY,
        fontweight=weight,
        color=TEXT_PRIMARY
    )
    return box


def draw_arrow(ax, start, end, color=ARROW_COLOR):
    """Draw an arrow between two points."""
    ax.annotate(
        '',
        xy=end,
        xytext=start,
        arrowprops=dict(
            arrowstyle='->',
            color=color,
            lw=1.5,
            connectionstyle='arc3,rad=0'
        )
    )


def create_agent_experiment_diagram():
    """Create the agent experiment trajectory diagram."""
    
    # Create figure
    fig, ax = plt.subplots(figsize=(CANVAS_WIDTH, CANVAS_HEIGHT))
    ax.set_xlim(0, CANVAS_WIDTH)
    ax.set_ylim(0, CANVAS_HEIGHT)
    ax.axis('off')
    
    # Set background
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Draw title
    ax.text(
        CANVAS_WIDTH / 2, 
        CANVAS_HEIGHT - 0.4,
        "Agent Experiments as Trajectories Through Environments",
        ha='center',
        va='top',
        fontsize=16,
        fontfamily=FONT_FAMILY,
        fontweight='bold',
        color=TEXT_PRIMARY
    )
    
    # Flow items from top to bottom
    # Format: (label, color, fontsize, bold)
    items = [
        ("Environment State", NODE_FILL, 12, True),
        ("Agent Action", NODE_FILL, 11, False),
        ("State Transition", NODE_FILL, 11, False),
        ("Artifact Recorded", ARTIFACT_COLOR, 11, True),
        ("Evaluation", EVALUATION_COLOR, 12, True),
        ("Experiment Dataset", NODE_FILL, 11, False),
    ]
    
    # Box dimensions
    box_width = 5.0
    box_height = 0.9
    start_x = (CANVAS_WIDTH - box_width) / 2
    start_y = CANVAS_HEIGHT - 1.5
    gap = 0.6
    
    # Draw boxes and arrows
    for i, (text, color, fontsize, bold) in enumerate(items):
        y = start_y - i * (box_height + gap)
        draw_box(ax, start_x, y, box_width, box_height, text, color, fontsize, bold)
        
        # Add arrow between boxes (except for last item)
        if i < len(items) - 1:
            arrow_y = y - gap / 2
            draw_arrow(
                ax,
                (start_x + box_width / 2, arrow_y + 0.2),
                (start_x + box_width / 2, arrow_y - 0.2)
            )
    
    # Add subtle labels on the side
    # Top label - entry point
    ax.text(
        start_x + box_width + 0.4,
        start_y + box_height / 2,
        "t=0",
        ha='left',
        va='center',
        fontsize=10,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    # Middle label - trajectory
    ax.text(
        start_x + box_width + 0.4,
        start_y - 2 * (box_height + gap) + box_height / 2,
        "trajectory",
        ha='left',
        va='center',
        fontsize=10,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    # Bottom label - dataset
    ax.text(
        start_x + box_width + 0.4,
        start_y - 5 * (box_height + gap) + box_height / 2,
        "collected",
        ha='left',
        va='center',
        fontsize=10,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    # Add highlight annotations
    # Artifact highlight
    artifact_y = start_y - 3 * (box_height + gap) + box_height / 2
    ax.annotate(
        '',
        xy=(start_x - 0.15, artifact_y + box_height / 2 + 0.05),
        xytext=(start_x - 0.15, artifact_y - box_height / 2 - 0.05),
        arrowprops=dict(
            arrowstyle='-',
            color='#ffb300',
            lw=2,
        )
    )
    ax.text(
        start_x - 0.25,
        artifact_y,
        "recorded",
        ha='right',
        va='center',
        fontsize=9,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color='#ffb300'
    )
    
    # Evaluation highlight
    eval_y = start_y - 4 * (box_height + gap) + box_height / 2
    ax.annotate(
        '',
        xy=(start_x - 0.15, eval_y + box_height / 2 + 0.05),
        xytext=(start_x - 0.15, eval_y - box_height / 2 - 0.05),
        arrowprops=dict(
            arrowstyle='-',
            color='#1976d2',
            lw=2,
        )
    )
    ax.text(
        start_x - 0.25,
        eval_y,
        "scored",
        ha='right',
        va='center',
        fontsize=9,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color='#1976d2'
    )
    
    plt.tight_layout()
    
    # Save outputs
    output_svg = "docs/figures/agent_experiment_trajectory.svg"
    output_png = "docs/figures/agent_experiment_trajectory.png"
    
    fig.savefig(output_svg, format='svg', dpi=150, bbox_inches='tight', facecolor='white')
    fig.savefig(output_png, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    
    plt.close(fig)
    
    print(f"Generated: {output_svg}")
    print(f"Generated: {output_png}")


if __name__ == "__main__":
    create_agent_experiment_diagram()
