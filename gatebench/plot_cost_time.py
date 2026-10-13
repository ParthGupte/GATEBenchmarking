"""
Generation cost and generation time figures (the graphical companions to
Tables I and II).

Values are summed per (paper, model, year) across that paper's 65 questions,
so they are the total dollars/minutes spent benchmarking one model on one
paper -- not a per-question average. Rows with a null time/cost (buffer
questions that were never queried) are excluded from the sum.

Cost and time are the figures reported by the API provider for each
generation; see data/README.md.

Run:  python -m gatebench.plot_cost_time
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from gatebench.config import (
    EXAM_DURATION_MIN, FIGURES_DIR, MODEL_DIR_LABELS, MODELS, PAPERS,
    RESULTS_DIR, YEARS,
)
from gatebench.plotstyle import (
    BASE_WIDTH, BLUE, LABEL_SIZE, LEGEND_SIZE, NARROW, ORANGE, TICK_SIZE,
    TITLE_SIZE, VALUE_SIZE as REGULAR_VALUE_SIZE, outline,
)

SUPTITLE_SIZE = 26
VALUE_SIZE = 13
BAR_WIDTH = 0.4

# A bar shorter than this fraction of the axis height can't fit the rotated
# value label inside itself without it spilling out the top -- put the label
# above the bar instead, in dark text on the white background, for those.
MIN_INSIDE_LABEL_FRAC = 0.2


def _iter_rows():
    for path in sorted(RESULTS_DIR.glob("*/*/*.json")):
        model_dir, year, filename = path.parts[-3], path.parts[-2], path.parts[-1]
        model_label = MODEL_DIR_LABELS.get(model_dir)
        paper = Path(filename).stem.split("_")[0]
        if model_label is None or year not in YEARS or paper not in PAPERS:
            continue
        for row in json.load(open(path)):
            if row["question_type"] is None:
                continue
            yield model_label, paper, year, row


def compute_totals(field: str) -> dict[tuple[str, str, str], float]:
    sums = defaultdict(float)
    for model_label, paper, year, row in _iter_rows():
        value = row.get(field)
        if value is None:
            continue
        sums[(paper, model_label, year)] += value
    return dict(sums)


def compute_averages_by_model(field: str) -> dict[tuple[str, str], float]:
    """(model, year) -> average per question, across all papers."""
    sums = defaultdict(lambda: [0.0, 0])
    for model_label, _paper, year, row in _iter_rows():
        value = row.get(field)
        if value is None:
            continue
        sums[(model_label, year)][0] += value
        sums[(model_label, year)][1] += 1
    return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in sums.items()}


def compute_averages_by_paper(field: str) -> dict[tuple[str, str], float]:
    """(paper, year) -> average per question, across all models."""
    sums = defaultdict(lambda: [0.0, 0])
    for _model_label, paper, year, row in _iter_rows():
        value = row.get(field)
        if value is None:
            continue
        sums[(paper, year)][0] += value
        sums[(paper, year)][1] += 1
    return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in sums.items()}


def plot_grid(fname, title, ylabel, averages, fmt, ylim=None,
              reference_line=None, reference_label=None):
    x = np.arange(len(MODELS))
    fig, axes = plt.subplots(3, 2, figsize=(14, 15))
    axes = axes.flatten()

    for ax, paper in zip(axes, PAPERS):
        vals_2025 = [averages.get((paper, m, "2025"), 0.0) for m in MODELS]
        vals_2026 = [averages.get((paper, m, "2026"), 0.0) for m in MODELS]

        bars_2025 = ax.bar(x - BAR_WIDTH / 2, vals_2025, BAR_WIDTH,
                           label="2025", color=BLUE, edgecolor="black")
        bars_2026 = ax.bar(x + BAR_WIDTH / 2, vals_2026, BAR_WIDTH,
                           label="2026", color=ORANGE, edgecolor="black")

        if ylim is not None:
            ax.set_ylim(*ylim)
        else:
            top = max(vals_2025 + vals_2026 + ([reference_line] if reference_line else [0]))
            ax.set_ylim(0, top * 1.2)
        y_top = ax.get_ylim()[1]

        if reference_line is not None:
            ax.axhline(reference_line, color="black", linestyle="--", linewidth=2, zorder=5)
            # Labeled inline (not via the legend) so the legend box doesn't
            # grow and start overlapping the tall bars. Anchored at the left
            # edge, consistently the shortest bar across every paper.
            ax.text(-0.45, reference_line + 0.015 * y_top, reference_label,
                    ha="left", va="bottom", fontsize=LEGEND_SIZE * 0.7,
                    fontweight="bold", zorder=6)

        for bars in (bars_2025, bars_2026):
            for bar in bars:
                h = bar.get_height()
                if h < MIN_INSIDE_LABEL_FRAC * y_top:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.02 * y_top,
                            format(h, fmt), ha="center", va="bottom",
                            rotation=90, fontsize=VALUE_SIZE, fontweight="bold",
                            color="black", zorder=6)
                else:
                    ax.text(bar.get_x() + bar.get_width() / 2, h - 0.02 * y_top,
                            format(h, fmt), ha="center", va="top",
                            rotation=90, fontsize=VALUE_SIZE, fontweight="bold",
                            color="white", zorder=6, path_effects=outline())

        ax.set_title(paper, fontsize=TITLE_SIZE)
        ax.set_xlabel("MODEL", fontsize=LABEL_SIZE)
        ax.set_ylabel(ylabel, fontsize=LABEL_SIZE)
        ax.set_xticks(x)
        ax.set_xticklabels(MODELS, rotation=45, ha="right")
        ax.tick_params(axis="both", labelsize=TICK_SIZE)
        ax.legend(loc="best", fontsize=LEGEND_SIZE)

    fig.suptitle(title, fontsize=SUPTITLE_SIZE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    FIGURES_DIR.mkdir(exist_ok=True)
    path = FIGURES_DIR / fname
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print("Saved", path)


def plot_single_regular(fname, title, categories, series, xlabel, ylabel, *,
                        width, fmt, legend_loc="best", rotation=45):
    """Single-panel bar chart at the full-size, scale-aware label size, with
    overflow-safe placement: a bar too short for the label to fit inside puts
    it above the bar instead."""
    x = np.arange(len(categories))
    n = len(series)
    offsets = (np.arange(n) - (n - 1) / 2) * width
    scale = NARROW["figsize"][0] / BASE_WIDTH
    value_size = REGULAR_VALUE_SIZE * scale

    fig, ax = plt.subplots(figsize=NARROW["figsize"])
    drawn = []
    for (label, color, values), off in zip(series, offsets):
        drawn.append(ax.bar(x + off, values, width, label=label, color=color,
                            edgecolor="black", linewidth=NARROW["linewidth"]))

    all_vals = [v for _, _, values in series for v in values]
    ax.set_ylim(0, max(all_vals) * 1.2)
    y_top = ax.get_ylim()[1]

    for bars in drawn:
        for bar in bars:
            h = bar.get_height()
            if h < MIN_INSIDE_LABEL_FRAC * y_top:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.015 * y_top,
                        format(h, fmt), ha="center", va="bottom",
                        rotation=90, fontsize=value_size, fontweight="bold",
                        color="black", zorder=6)
            else:
                ax.text(bar.get_x() + bar.get_width() / 2, h - 0.015 * y_top,
                        format(h, fmt), ha="center", va="top",
                        rotation=90, fontsize=value_size, fontweight="bold",
                        color="white", zorder=6, path_effects=outline(scale))

    ax.set_title(title, fontsize=TITLE_SIZE * scale)
    ax.set_xlabel(xlabel, fontsize=LABEL_SIZE * scale)
    ax.set_ylabel(ylabel, fontsize=LABEL_SIZE * scale)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=rotation, ha="right" if rotation else "center")
    ax.tick_params(axis="both", labelsize=TICK_SIZE * scale)
    ax.legend(loc=legend_loc, fontsize=LEGEND_SIZE * scale)

    fig.tight_layout()
    FIGURES_DIR.mkdir(exist_ok=True)
    path = FIGURES_DIR / fname
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print("Saved", path)


def main() -> None:
    cost_total = compute_totals("generation_cost")
    # Minutes, not seconds: a total over 65 questions would otherwise produce
    # unwieldy 5-digit bar labels.
    time_total_min = {k: v / 60 for k, v in compute_totals("generation_time_s").items()}

    plot_grid(
        "combined_model_comparison_2025_vs_2026_cost.png",
        "TOTAL GENERATION COST BY PAPER (2025 VS 2026)",
        "TOTAL COST (USD)", cost_total, fmt=".2f",
    )
    plot_grid(
        "combined_model_comparison_2025_vs_2026_time.png",
        "TOTAL GENERATION TIME BY PAPER (2025 VS 2026)",
        "TOTAL TIME (min)", time_total_min, fmt=".2f",
        reference_line=EXAM_DURATION_MIN,
        reference_label=f"{EXAM_DURATION_MIN} min (exam duration)",
    )

    cost_avg_by_model = compute_averages_by_model("generation_cost")
    cost_avg_by_paper = compute_averages_by_paper("generation_cost")

    plot_single_regular(
        "modelwise_cost_2025_vs_2026.png",
        "AVERAGE GENERATION COST PER QUESTION BY MODEL (2025 VS 2026)", MODELS,
        [(year, {"2025": BLUE, "2026": ORANGE}[year],
          [cost_avg_by_model.get((m, year), 0.0) for m in MODELS])
         for year in YEARS],
        "MODEL", "AVG COST / QUESTION (USD)", width=0.35, fmt=".3f",
        legend_loc="upper right")

    plot_single_regular(
        "subjectwise_cost_2025_vs_2026.png",
        "AVERAGE GENERATION COST PER QUESTION BY TEST PAPER (2025 VS 2026)", PAPERS,
        [(year, {"2025": BLUE, "2026": ORANGE}[year],
          [cost_avg_by_paper.get((p, year), 0.0) for p in PAPERS])
         for year in YEARS],
        "TEST PAPERS", "AVG COST / QUESTION (USD)", width=0.25, fmt=".3f",
        rotation=0, legend_loc="upper right")


if __name__ == "__main__":
    main()
