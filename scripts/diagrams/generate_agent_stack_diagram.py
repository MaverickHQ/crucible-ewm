#!/usr/bin/env python3
"""
Generate the Executable Agent Stack diagram.

This script creates a publication-quality stacked layer architecture diagram
showing the layers of the agent system.
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
CANVAS_WIDTH = 12
CANVAS_HEIGHT = 10

# Colors for layers
ENVIRONMENT_COLOR = "#e8f4ea"  # Light green - foundation
AGENTS_COLOR = "#fff3e0"  # Light orange - highlighted
DEFAULT_COLOR = "#fafafa"  # White-ish default


def create_agent_stack_diagram():
    """Create the agent stack diagram."""
    
    # Define layers from top to bottom
    layers = [
        ("Tokens", DEFAULT_COLOR),
        ("Models", DEFAULT_COLOR),
        ("Agents", AGENTS_COLOR),
        ("Constraints", DEFAULT_COLOR),
        ("Artifacts", DEFAULT_COLOR),
        ("Evaluation", DEFAULT_COLOR),
        ("Experiments", DEFAULT_COLOR),
        ("Environments", ENVIRONMENT_COLOR),
    ]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(CANVAS_WIDTH, CANVAS_HEIGHT))
    ax.set_xlim(0, CANVAS_WIDTH)
    ax.set_ylim(0, CANVAS_HEIGHT)
    ax.axis('off')
    
    # Set background
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Calculate dimensions
    layer_height = 0.9
    layer_width = 8
    start_x = (CANVAS_WIDTH - layer_width) / 2
    gap = 0.15
    
    # Draw title
    ax.text(
        CANVAS_WIDTH / 2, 
        CANVAS_HEIGHT - 0.5,
        "The Executable Agent Stack",
        ha='center',
        va='top',
        fontsize=20,
        fontfamily=FONT_FAMILY,
        fontweight='bold',
        color=TEXT_PRIMARY
    )
    
    # Draw layers from top to bottom
    for i, (layer_name, fill_color) in enumerate(layers):
        y_pos = CANVAS_HEIGHT - 1.5 - i * (layer_height + gap)
        
        # Draw box
        box = FancyBboxPatch(
            (start_x, y_pos),
            layer_width,
            layer_height,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            facecolor=fill_color,
            edgecolor=NODE_BORDER,
            linewidth=1.5
        )
        ax.add_patch(box)
        
        # Add layer name
        ax.text(
            start_x + layer_width / 2,
            y_pos + layer_height / 2,
            layer_name,
            ha='center',
            va='center',
            fontsize=14,
            fontfamily=FONT_FAMILY,
            fontweight='medium',
            color=TEXT_PRIMARY
        )
        
        # Add vertical arrow connecting layers (except for top layer)
        if i < len(layers) - 1:
            arrow_y = y_pos - gap / 2
            ax.annotate(
                '',
                xy=(start_x + layer_width / 2, arrow_y - 0.15),
                xytext=(start_x + layer_width / 2, arrow_y + 0.15),
                arrowprops=dict(
                    arrowstyle='->',
                    color=ARROW_COLOR,
                    lw=1.2
                )
            )
    
    # Add subtle foundation label
    ax.text(
        start_x + layer_width + 0.3,
        CANVAS_HEIGHT - 1.5 - 7 * (layer_height + gap) + layer_height / 2,
        "Foundation",
        ha='left',
        va='center',
        fontsize=10,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    # Add subtle agent label
    ax.text(
        start_x + layer_width + 0.3,
        CANVAS_HEIGHT - 1.5 - 2 * (layer_height + gap) + layer_height / 2,
        "Core",
        ha='left',
        va='center',
        fontsize=10,
        fontfamily=FONT_FAMILY,
        fontstyle='italic',
        color=TEXT_SECONDARY
    )
    
    plt.tight_layout()
    
    # Save outputs
    output_svg = "docs/figures/agent_stack.svg"
    output_png = "docs/figures/agent_stack.png"
    
    fig.savefig(output_svg, format='svg', dpi=150, bbox_inches='tight', facecolor='white')
    fig.savefig(output_png, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    
    plt.close(fig)
    
    print(f"Generated: {output_svg}")
    print(f"Generated: {output_png}")


if __name__ == "__main__":
    create_agent_stack_diagram()
