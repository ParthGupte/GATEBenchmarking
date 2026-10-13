"""
Generate Figures 1-9 of the paper from results/.

Every figure reports the same metric: pooled marks-percent,
sum(marks_obtained, treating a null/unattempted question as 0) /
sum(marks) * 100. This bakes in GATE's official negative marking for wrong
MCQ answers and counts voided "marks to all" questions as full marks.

AIR-1 scores are external reference data read from data/air1_scores.json.

Run:  python -m gatebench.plot_figures
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from gatebench.config import (
    AIR1_PATH, FIGURES_DIR, MODEL_DIR_LABELS, MODELS, PAPERS, RESULTS_DIR, YEARS,
)
from gatebench.plotstyle import (
    BLUE, GREEN, LABEL_SIZE, LEGEND_SIZE, NARROW, ORANGE, PURE_GREEN, RED, TEAL,
    TICK_SIZE, TITLE_SIZE, WIDE, grouped_bar, outline,
)

QTYPES = ["MCQ", "MSQ", "NAT"]


def load_air1() -> dict[str, float]:
    return json.load(open(AIR1_PATH))["scores"]


def load_rows():
    """Yield (model_label, paper, year, row) for every scored question."""
    for path in sorted(RESULTS_DIR.glob("*/*/*.json")):
        model_dir, year, filename = path.parts[-3], path.parts[-2], path.parts[-1]
        model_label = MODEL_DIR_LABELS.get(model_dir)
        paper = Path(filename).stem.split("_")[0]
        if model_label is None or year not in YEARS or paper not in PAPERS:
            continue
        for row in json.load(open(path)):
            # Buffer questions carry no official key and are excluded.
            if row["question_type"] is None:
                continue
            yield model_label, paper, year, row


def compute_all():
    score_by_model_year = defaultdict(lambda: [0.0, 0.0])
    score_by_paper_year = defaultdict(lambda: [0.0, 0.0])
    score_by_paper_model_year = defaultdict(lambda: [0.0, 0.0])

    img_score_by_model_year = defaultdict(lambda: [0.0, 0.0])
    img_score_by_paper_year = defaultdict(lambda: [0.0, 0.0])

    qtype_score_by_model = defaultdict(lambda: [0.0, 0.0])
    qtype_score_by_paper = defaultdict(lambda: [0.0, 0.0])

    ga_by_model_year = defaultdict(lambda: [0.0, 0.0])
    ga_by_paper_year = defaultdict(lambda: [0.0, 0.0])

    for model_label, paper, year, row in load_rows():
        obtained = row["marks_obtained"] if row["marks_obtained"] is not None else 0
        marks = row["marks"]

        score_by_model_year[(model_label, year)][0] += obtained
        score_by_model_year[(model_label, year)][1] += marks
        score_by_paper_year[(paper, year)][0] += obtained
        score_by_paper_year[(paper, year)][1] += marks
        score_by_paper_model_year[(paper, model_label, year)][0] += obtained
        score_by_paper_model_year[(paper, model_label, year)][1] += marks

        ga_group = "GA" if row["section"] == "GA" else "SUBJECT"
        ga_by_model_year[(model_label, year, ga_group)][0] += obtained
        ga_by_model_year[(model_label, year, ga_group)][1] += marks
        ga_by_paper_year[(paper, year, ga_group)][0] += obtained
        ga_by_paper_year[(paper, year, ga_group)][1] += marks

        image_group = "IMAGE" if row["has_image"] else "NO IMAGE"
        for agg, key in (
            (img_score_by_model_year, (model_label, year, image_group)),
            (img_score_by_paper_year, (paper, year, image_group)),
            (qtype_score_by_model, (model_label, row["question_type"])),
            (qtype_score_by_paper, (paper, row["question_type"])),
        ):
            agg[key][0] += obtained
            agg[key][1] += marks

    def pct(obtained, possible):
        return 100 * obtained / possible if possible else 0.0

    return {
        "score_by_model_year": {k: pct(*v) for k, v in score_by_model_year.items()},
        "score_by_paper_year": {k: pct(*v) for k, v in score_by_paper_year.items()},
        "score_by_paper_model_year": {k: pct(*v) for k, v in score_by_paper_model_year.items()},
        "img_score_by_model_year": {k: pct(*v) for k, v in img_score_by_model_year.items()},
        "img_score_by_paper_year": {k: pct(*v) for k, v in img_score_by_paper_year.items()},
        "qtype_score_by_model": {k: pct(*v) for k, v in qtype_score_by_model.items()},
        "qtype_score_by_paper": {k: pct(*v) for k, v in qtype_score_by_paper.items()},
        "ga_by_model_year": {k: pct(*v) for k, v in ga_by_model_year.items()},
        "ga_by_paper_year": {k: pct(*v) for k, v in ga_by_paper_year.items()},
    }


def plot_paper_model_grid(score_by_paper_model_year, air1):
    """Figure 1: 3x2 per-paper model-vs-AIR-1 comparison grid."""
    BAR_WIDTH = 0.4
    YLIM = (30, 100)
    SUPTITLE_SIZE = 26
    # Smaller than the other figures' 20: short bars need a label that fits.
    VALUE_SIZE = 13

    x = np.arange(len(MODELS))
    fig, axes = plt.subplots(3, 2, figsize=(14, 15))
    axes = axes.flatten()

    for ax, paper in zip(axes, PAPERS):
        air1_score = air1[paper]
        vals_2025 = [score_by_paper_model_year[(paper, m, "2025")] for m in MODELS]
        vals_2026 = [score_by_paper_model_year[(paper, m, "2026")] for m in MODELS]

        line = ax.axhline(air1_score, color="black", linestyle="--", linewidth=3, zorder=5)
        bars_2025 = ax.bar(x - BAR_WIDTH / 2, vals_2025, BAR_WIDTH,
                           label="2025", color=BLUE, edgecolor="black")
        bars_2026 = ax.bar(x + BAR_WIDTH / 2, vals_2026, BAR_WIDTH,
                           label="2026", color=ORANGE, edgecolor="black")

        for bars in (bars_2025, bars_2026):
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 1.5,
                        f"{bar.get_height():.2f}", ha="center", va="top",
                        rotation=90, fontsize=VALUE_SIZE, fontweight="bold",
                        color="white", zorder=6, path_effects=outline())

        ax.set_title(paper, fontsize=TITLE_SIZE)
        ax.set_xlabel("MODEL", fontsize=LABEL_SIZE)
        ax.set_ylabel("SCORE (%)", fontsize=LABEL_SIZE)
        ax.set_ylim(*YLIM)
        ax.set_yticks(np.arange(YLIM[0], YLIM[1] + 1, 10))
        ax.set_xticks(x)
        ax.set_xticklabels(MODELS, rotation=45, ha="right")
        ax.tick_params(axis="both", labelsize=TICK_SIZE)
        ax.legend([line, bars_2025, bars_2026],
                  [f"AIR-1 (2026): {air1_score:.2f}", "2025", "2026"],
                  loc="lower left", fontsize=LEGEND_SIZE)

    fig.suptitle("MODEL COMPARISON ACROSS PAPERS (2025 VS 2026 VS AIR-1)",
                 fontsize=SUPTITLE_SIZE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    path = FIGURES_DIR / "combined_model_comparison_2025_vs_2026_vs_air1_3x2.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print("Saved", path)


def main() -> None:
    FIGURES_DIR.mkdir(exist_ok=True)
    out = str(FIGURES_DIR)
    data = compute_all()
    air1 = load_air1()

    # --- Figure 1 ----------------------------------------------------------
    plot_paper_model_grid(data["score_by_paper_model_year"], air1)

    # --- Figure 2: average performance per test paper ----------------------
    subject_series = [(year, {"2025": BLUE, "2026": ORANGE}[year],
                       [data["score_by_paper_year"][(p, year)] for p in PAPERS])
                      for year in YEARS]
    subject_series.append(("AIR-1 (2026)", PURE_GREEN, [air1[p] for p in PAPERS]))
    grouped_bar(
        out, "subject_average_across_models_2025_vs_2026.png",
        "AVERAGE PERFORMANCE ACROSS MODELS BY TEST PAPERS\n"
        "(2025 VS 2026 VS AIR-1)",
        PAPERS, subject_series,
        "TEST PAPERS", "AVERAGE SCORE (%)", width=0.25, fmt=".2f",
        ylim=(30, 100), rotation=0, **NARROW)

    # --- Figures 3 & 4: image vs no-image score -------------------------
    IMG_SERIES = ["IMAGE 2025", "NO IMAGE 2025", "IMAGE 2026", "NO IMAGE 2026"]
    IMG_COLORS = [BLUE, TEAL, ORANGE, RED]
    img_series_specs = [
        (label, color, year, group)
        for label, color, (year, group) in zip(
            IMG_SERIES, IMG_COLORS,
            [("2025", "IMAGE"), ("2025", "NO IMAGE"), ("2026", "IMAGE"), ("2026", "NO IMAGE")])
    ]

    grouped_bar(
        out, "paperwise_image_vs_noimage_2025_vs_2026.png",
        "PAPERWISE IMAGE VS NO IMAGE SCORE (2025 VS 2026)", PAPERS,
        [(label, color, [data["img_score_by_paper_year"].get((p, year, group), 0.0) for p in PAPERS])
         for label, color, year, group in img_series_specs],
        "TEST PAPERS", "AVERAGE SCORE (%)", width=0.18, ylim=(0, 100), **WIDE)

    grouped_bar(
        out, "modelwise_image_vs_noimage_2025_vs_2026.png",
        "MODELWISE IMAGE VS NO IMAGE SCORE (2025 VS 2026)", MODELS,
        [(label, color, [data["img_score_by_model_year"].get((m, year, group), 0.0) for m in MODELS])
         for label, color, year, group in img_series_specs],
        "MODEL", "AVERAGE SCORE (%)", width=0.18, ylim=(0, 100), **WIDE)

    # --- Figures 5 & 6: question-type score -----------------------------
    QCOLORS = [BLUE, ORANGE, GREEN]

    grouped_bar(
        out, "modelwise_question_type_accuracy.png",
        "MODELWISE QUESTION TYPE SCORE", MODELS,
        list(zip(QTYPES, QCOLORS,
                 [[data["qtype_score_by_model"].get((m, qt), 0.0) for m in MODELS] for qt in QTYPES])),
        "MODEL", "AVERAGE SCORE (%)", width=0.8 / 3, ylim=(0, 100), **WIDE)

    grouped_bar(
        out, "paperwise_question_type_accuracy.png",
        "PAPERWISE QUESTION TYPE SCORE", PAPERS,
        list(zip(QTYPES, QCOLORS,
                 [[data["qtype_score_by_paper"].get((p, qt), 0.0) for p in PAPERS] for qt in QTYPES])),
        "TEST PAPERS", "AVERAGE SCORE (%)", width=0.8 / 3, ylim=(0, 100), **WIDE)

    # --- Figures 7 & 8: General Aptitude vs subject ------------------------
    GA_SERIES = ["GA 2025", "SUBJECT 2025", "GA 2026", "SUBJECT 2026"]
    GA_COLORS = [BLUE, TEAL, ORANGE, RED]
    ga_series_specs = [
        (label, color, year, group)
        for label, color, (year, group) in zip(
            GA_SERIES, GA_COLORS,
            [("2025", "GA"), ("2025", "SUBJECT"), ("2026", "GA"), ("2026", "SUBJECT")])
    ]

    grouped_bar(
        out, "modelwise_ga_vs_subject_2025_vs_2026.png",
        "MODELWISE GENERAL APTITUDE VS SUBJECT SCORE (%) (2025 VS 2026)",
        MODELS,
        [(label, color, [data["ga_by_model_year"].get((m, year, group), 0.0) for m in MODELS])
         for label, color, year, group in ga_series_specs],
        "MODEL", "SCORE (%)", width=0.18, ylim=(0, 100), **WIDE)

    grouped_bar(
        out, "subjectwise_ga_vs_subject_2025_vs_2026.png",
        "SUBJECTWISE GENERAL APTITUDE VS SUBJECT SCORE (%) (2025 VS 2026)",
        PAPERS,
        [(label, color, [data["ga_by_paper_year"].get((p, year, group), 0.0) for p in PAPERS])
         for label, color, year, group in ga_series_specs],
        "TEST PAPERS", "SCORE (%)", width=0.18, ylim=(0, 100), **WIDE)

    # --- Figure 9: overall model performance -------------------------------
    grouped_bar(
        out, "overall_model_performance_2025_vs_2026.png",
        "OVERALL MODEL PERFORMANCE: 2025 VS 2026", MODELS,
        [(year, {"2025": BLUE, "2026": ORANGE}[year],
          [data["score_by_model_year"][(m, year)] for m in MODELS])
         for year in YEARS],
        "MODEL", "AVERAGE SCORE (%)", width=0.35, fmt=".2f",
        ylim=(30, 100), legend_loc="lower left", **NARROW)


if __name__ == "__main__":
    main()
