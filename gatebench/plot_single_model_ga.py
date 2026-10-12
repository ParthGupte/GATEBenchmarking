"""
Supplementary figure: General Aptitude vs subject marks-percent for a single
model, one bar group per test paper. Same style as the aggregated GA figures
(Figures 7 and 8), restricted to one model instead of all seven.

Run:  python -m gatebench.plot_single_model_ga [model_dir]

model_dir defaults to gpt-5.5-20260423 and must be a directory name under
data/responses/.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

from gatebench.config import (
    FIGURES_DIR, MODEL_DIR_LABELS, PAPERS, RESULTS_DIR, YEARS,
)
from gatebench.plotstyle import BLUE, ORANGE, RED, TEAL, WIDE, grouped_bar

DEFAULT_MODEL = "gpt-5.5-20260423"


def main() -> None:
    model_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    if model_dir not in MODEL_DIR_LABELS:
        sys.exit(f"Unknown model_dir {model_dir!r}. Choices: {sorted(MODEL_DIR_LABELS)}")
    label = MODEL_DIR_LABELS[model_dir]

    agg = defaultdict(lambda: [0.0, 0.0])  # (paper, year, group) -> [obtained, possible]
    for paper in PAPERS:
        for year in YEARS:
            path = RESULTS_DIR / model_dir / year / f"{paper}_{year}.json"
            for row in json.load(open(path)):
                if row["question_type"] is None:
                    continue
                group = "GA" if row["section"] == "GA" else "SUBJECT"
                obtained = row["marks_obtained"] if row["marks_obtained"] is not None else 0
                agg[(paper, year, group)][0] += obtained
                agg[(paper, year, group)][1] += row["marks"]

    def pct(paper, year, group):
        obtained, possible = agg[(paper, year, group)]
        return 100 * obtained / possible if possible else 0.0

    FIGURES_DIR.mkdir(exist_ok=True)
    grouped_bar(
        str(FIGURES_DIR),
        f"{model_dir}_ga_vs_subject_2025_vs_2026.png",
        f"{label} GENERAL APTITUDE VS SUBJECT MARKS PERCENT (2025 VS 2026)",
        PAPERS,
        [("GA 2025", BLUE, [pct(p, "2025", "GA") for p in PAPERS]),
         ("SUBJECT 2025", TEAL, [pct(p, "2025", "SUBJECT") for p in PAPERS]),
         ("GA 2026", ORANGE, [pct(p, "2026", "GA") for p in PAPERS]),
         ("SUBJECT 2026", RED, [pct(p, "2026", "SUBJECT") for p in PAPERS])],
        "TEST PAPERS", "MARKS PERCENT", width=0.18, ylim=(0, 100), **WIDE)


if __name__ == "__main__":
    main()
