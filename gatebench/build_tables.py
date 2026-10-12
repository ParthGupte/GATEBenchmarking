"""
Build Tables I and II of the paper as LaTeX (booktabs).

Rows are test papers, columns are models, and each cell shows the 2025 and
2026 value separated by a slash. The rightmost column averages across models
for that paper, the bottom row averages across papers for that model, and the
bottom-right cell is the overall average -- all per question, whereas the body
of the table holds per-paper totals.

Run:  python -m gatebench.build_tables
"""

from __future__ import annotations

from gatebench.config import (
    EXAM_DURATION_MIN, MODELS, PAPERS, QUESTIONS_PER_PAPER, TABLES_DIR, YEARS,
)
from gatebench.plot_cost_time import (
    compute_averages_by_model, compute_averages_by_paper, compute_totals,
)

OUT_PATH = TABLES_DIR / "cost_time_tables.tex"


def grand_average(total_dict) -> dict[str, float]:
    """Overall per-question average across every paper and model, per year."""
    n = len(PAPERS) * len(MODELS) * QUESTIONS_PER_PAPER
    return {
        year: sum(v for (_p, _m, y), v in total_dict.items() if y == year) / n
        for year in YEARS
    }


def cell(v25, v26, fmt, bold_threshold=None) -> str:
    s25, s26 = fmt(v25), fmt(v26)
    if bold_threshold is not None:
        if v25 > bold_threshold:
            s25 = rf"\textbf{{{s25}}}"
        if v26 > bold_threshold:
            s26 = rf"\textbf{{{s26}}}"
    return f"{s25} / {s26}"


def build_table(total_dict, avg_model_dict, avg_paper_dict, grand_avg, fmt,
                caption, label, bold_threshold=None) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{l" + "c" * len(MODELS) + "|c}",
        r"\toprule",
    ]
    header = ([r"\textbf{Paper}"]
              + [rf"\textbf{{{m}}}" for m in MODELS]
              + [r"\textbf{Average}"])
    lines.append(" & ".join(header) + r" \\")
    lines.append(r"\midrule")

    for paper in PAPERS:
        row = [paper]
        for model in MODELS:
            row.append(cell(total_dict.get((paper, model, "2025"), 0.0),
                            total_dict.get((paper, model, "2026"), 0.0),
                            fmt, bold_threshold))
        row.append(rf"\textit{{{cell(avg_paper_dict.get((paper, '2025'), 0.0), avg_paper_dict.get((paper, '2026'), 0.0), fmt)}}}")
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    row = [r"\textbf{Average}"]
    for model in MODELS:
        row.append(rf"\textit{{{cell(avg_model_dict.get((model, '2025'), 0.0), avg_model_dict.get((model, '2026'), 0.0), fmt)}}}")
    row.append(rf"\textit{{{cell(grand_avg['2025'], grand_avg['2026'], fmt)}}}")
    lines.append(" & ".join(row) + r" \\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def cost_fmt(v: float) -> str:
    return f"{v:.3f}" if v < 1 else f"{v:.2f}"


def time_fmt(v: float) -> str:
    return f"{v:.1f}"


def main() -> None:
    cost_total = compute_totals("generation_cost")
    time_total_min = {k: v / 60 for k, v in compute_totals("generation_time_s").items()}

    cost_table = build_table(
        cost_total,
        compute_averages_by_model("generation_cost"),
        compute_averages_by_paper("generation_cost"),
        grand_average(cost_total),
        cost_fmt,
        caption=(
            "Total generation cost (USD) by test paper and model, shown as "
            "2025\\,/\\,2026. The rightmost column and bottom row give the "
            "average cost per question (2025\\,/\\,2026) for that paper (across "
            "all models) and that model (across all papers) respectively; the "
            "bottom-right cell is the overall average cost per question."
        ),
        label="tab:generation-cost",
    )

    time_avg_model = {k: v / 60 for k, v in compute_averages_by_model("generation_time_s").items()}
    time_avg_paper = {k: v / 60 for k, v in compute_averages_by_paper("generation_time_s").items()}

    time_table = build_table(
        time_total_min, time_avg_model, time_avg_paper,
        grand_average(time_total_min), time_fmt,
        caption=(
            "Total generation time (minutes) by test paper and model, shown as "
            f"2025\\,/\\,2026 (bold values exceed the {EXAM_DURATION_MIN}-minute exam "
            "duration). The rightmost column and bottom row give the average "
            "time per question (2025\\,/\\,2026) for that paper (across all "
            "models) and that model (across all papers) respectively; the "
            "bottom-right cell is the overall average time per question."
        ),
        label="tab:generation-time",
        bold_threshold=float(EXAM_DURATION_MIN),
    )

    TABLES_DIR.mkdir(exist_ok=True)
    out = ("% Requires: \\usepackage{booktabs}\n\n"
           + cost_table + "\n\n\n" + time_table + "\n")
    OUT_PATH.write_text(out)
    print("Saved", OUT_PATH)


if __name__ == "__main__":
    main()
