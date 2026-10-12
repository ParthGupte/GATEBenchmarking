"""
Shared figure styling.

Every figure in the paper is drawn through these helpers so that colours,
text sizes, bar geometry and value-label placement stay identical across the
whole set. Value labels sit inside their bar, rotated 90 degrees in bold
white with a dark outline, which keeps them legible on both pale and
saturated bars.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patheffects import withStroke  # noqa: E402

# Text sizes are quoted for a 14 in wide canvas and scaled up on wider figures
# (see BASE_WIDTH below).  Points are an absolute unit, so without this a 23 pt
# title on an 18 in figure renders at only 78% the apparent size once both are
# placed at the same width in a document.
BASE_WIDTH = 14.0
TITLE_SIZE = 23
LABEL_SIZE = 20
TICK_SIZE = 20
LEGEND_SIZE = 20
VALUE_SIZE = 20


def outline(scale=1.0):
    """Keeps the white labels legible over pale bars and legend frames."""
    return [withStroke(linewidth=2.5 * scale, foreground="black")]


BLUE, ORANGE, TEAL, RED, GREEN, PURE_GREEN = (
    "#1f77b4", "#ff7f0e", "#17becf", "#d62728", "#2ca02c", "#008000")


def label_bars(ax, bars, fmt, scale=1.0):
    """Write each bar's value inside the bar, rotated, bold white."""
    lo, hi = ax.get_ylim()
    offset = 0.015 * (hi - lo)
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h - offset, format(h, fmt),
                ha="center", va="top", rotation=90,
                fontsize=VALUE_SIZE * scale,
                fontweight="bold", color="white", zorder=6,
                path_effects=outline(scale))


def grouped_bar(outdir, fname, title, categories, series, xlabel, ylabel, *,
                figsize, width, linewidth, fmt, ylim=None,
                legend_loc="lower left", rotation=45):
    """series: list of (label, colour, values)."""
    x = np.arange(len(categories))
    n = len(series)
    offsets = (np.arange(n) - (n - 1) / 2) * width

    scale = figsize[0] / BASE_WIDTH
    fig, ax = plt.subplots(figsize=figsize)
    drawn = []
    for (label, color, values), off in zip(series, offsets):
        drawn.append(ax.bar(x + off, values, width, label=label, color=color,
                            edgecolor="black", linewidth=linewidth))

    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=TITLE_SIZE * scale)
    ax.set_xlabel(xlabel, fontsize=LABEL_SIZE * scale)
    ax.set_ylabel(ylabel, fontsize=LABEL_SIZE * scale)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=rotation,
                       ha="right" if rotation else "center")
    ax.tick_params(axis="both", labelsize=TICK_SIZE * scale)
    ax.legend(loc=legend_loc, fontsize=LEGEND_SIZE * scale)

    for bars in drawn:
        label_bars(ax, bars, fmt, scale)

    fig.tight_layout()
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, fname)
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print("Saved", path)


# Shared sizing presets.
NARROW = dict(figsize=(14, 7), linewidth=1.0)
WIDE = dict(figsize=(18, 8), linewidth=1.5, fmt=".2f")
