#!/usr/bin/env python3
"""
Generate the Tools vs Environment comparison diagram.

This script creates a publication-quality conceptual comparison showing
the difference between tool-based and environment-based agents.
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
CANVAS_WIDTH = 14
CANVAS_HEIGHT = 8

# Panel colors
GREY_PANEL = "#f7f7f7"
BLUE_PANEL = "#eef5ff"


def draw_box(ax, x, y, width, height, text, color=NODE_FILL, fontsize=12, bold=False):
    """Draw a box with text centered."""
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.08",
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


def create_tools_vs_environment_diagram():
    """Create the tools vs environment comparison diagram."""
    
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
        "Tools Return Results. Environments Produce Consequences.",
        ha='center',
        va='top',
        fontsize=18,
        fontfamily=FONT_FAMILY,
        fontweight='bold',
        color=TEXT_PRIMARY
    )
    
    # Panel dimensions
    panel_width = 5.5
    panel_height = 5.8
    panel_y = 1.0
    left_panel_x = 1.0
    right_panel_x = 7.5
    
    # Draw left panel background (grey)
    left_panel = FancyBboxPatch(
        (left_panel_x - 0.2, panel_y - 0.2),
        panel_width + 0.4,
        panel_height + 0.4,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=GREY_PANEL,
        edgecolor='none'
    )
    ax.add_patch(left_panel)
    
    # Draw right panel background (blue)
    right_panel = FancyBboxPatch(
        (right_panel_x - 0.2, panel_y - 0.2),
        panel_width + 0.4,
        panel_height + 0.4,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=BLUE_PANEL,
        edgecolor='none'
    )
    ax.add_patch(right_panel)
    
    # Left panel title
    ax.text(
        left_panel_x + panel_width / 2,
        panel_y + panel_height - 0.3,
        "Tool-Based Agent",
        ha='center',
        va='center',
        fontsize=14,
        fontfamily=FONT_FAMILY,
        fontweight='bold',
        color=TEXT_PRIMARY
    )
    
    # Right panel title
    ax.text(
        right_panel_x + panel_width / 2,
        panel_y + panel_height - 0.3,
        "Environment-Based Agent",
        ha='center',
        va='center',
        fontsize=14,
        fontfamily=FONT_FAMILY,
        fontweight='bold',
        color=TEXT_PRIMARY
    )
    
    # Left panel boxes (vertical stack)
    left_items = [
        ("Agent", NODE_FILL, 12, True),
        ("Tool Call", NODE_FILL, 11, False),
        ("Result", NODE_FILL, 12, False),
    ]
    
    left_box_width = 3.5
    left_box_height = 0.8
    left_start_y = panel_y + panel_height - 1.2
    left_gap = 0.6
    
    for i, (text, color, fontsize, bold) in enumerate(left_items):
        y = left_start_y - i * (left_box_height + left_gap)
        draw_box(ax, left_panel_x + (panel_width - left_box_width) / 2, y, 
                 left_box_width, left_box_height, text, color, fontsize, bold)
        
        # Add arrow between boxes
        if i < len(left_items) - 1:
            arrow_y = y - left_gap / 2
            draw_arrow(
                ax,
                (left_panel_x + panel_width / 2, arrow_y + 0.2),
                (left_panel_x + panel_width / 2, arrow_y - 0.2)
            )
    
    # Left panel footer text
    ax.text(
        left_panel_x + panel_width / 2,
        panel_y + 0.5,
        "World state unchanged",
        ha='center',
        va='center',
        fontsize=11,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    # Right panel boxes (vertical stack with loop)
    right_items = [
        ("Agent", NODE_FILL, 12, True),
        ("Action", NODE_FILL, 11, False),
        ("World State\nTransition", NODE_FILL, 10, False),
        ("New Observation", NODE_FILL, 10, False),
    ]
    
    right_box_width = 3.5
    right_box_height = 0.7
    right_start_y = panel_y + panel_height - 1.2
    right_gap = 0.5
    
    for i, (text, color, fontsize, bold) in enumerate(right_items):
        y = right_start_y - i * (right_box_height + right_gap)
        draw_box(ax, right_panel_x + (panel_width - right_box_width) / 2, y, 
                 right_box_width, right_box_height, text, color, fontsize, bold)
        
        # Add arrow between boxes
        if i < len(right_items) - 1:
            arrow_y = y - right_gap / 2
            draw_arrow(
                ax,
                (right_panel_x + panel_width / 2, arrow_y + 0.15),
                (right_panel_x + panel_width / 2, arrow_y - 0.15)
            )
    
    # Add feedback arrow from last box to Agent
    last_box_y = right_start_y - (len(right_items) - 1) * (right_box_height + right_gap)
    loop_start_y = last_box_y - 0.3
    loop_end_y = right_start_y + right_box_height + 0.3
    
    # Draw curved feedback arrow
    ax.annotate(
        '',
        xy=(right_panel_x + panel_width / 2 + 1.2, loop_end_y),
        xytext=(right_panel_x + panel_width / 2 + 1.2, loop_start_y),
        arrowprops=dict(
            arrowstyle='->',
            color=ARROW_COLOR,
            lw=1.5,
            connectionstyle='arc3,rad=0.3'
        )
    )
    
    # Add "back to Agent" label on the loop
    ax.text(
        right_panel_x + panel_width / 2 + 1.5,
        (loop_start_y + loop_end_y) / 2,
        "↺",
        ha='left',
        va='center',
        fontsize=14,
        color=ARROW_COLOR
    )
    
    # Right panel footer text
    ax.text(
        right_panel_x + panel_width / 2,
        panel_y + 0.5,
        "Actions change the state of the world",
        ha='center',
        va='center',
        fontsize=11,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    plt.tight_layout()
    
    # Save outputs
    output_svg = "docs/figures/tools_vs_environment.svg"
    output_png = "docs/figures/tools_vs_environment.png"
    
    fig.savefig(output_svg, format='svg', dpi=150, bbox_inches='tight', facecolor='white')
    fig.savefig(output_png, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    
    plt.close(fig)
    
    print(f"Generated: {output_svg}")
    print(f"Generated: {output_png}")


if __name__ == "__main__":
    create_tools_vs_environment_diagram()
