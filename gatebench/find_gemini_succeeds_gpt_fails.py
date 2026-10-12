"""
Find image-based questions where Gemini answered correctly but GPT answered
incorrectly, and dump full details (including each model's reasoning and
completion) into a single JSON file for qualitative inspection.

"Fails" means GPT gave a wrong answer (is_correct is False), not that GPT
never attempted the question (is_correct is None) -- the interesting case is
a genuine reasoning failure, not a missing data point.
"""

import json

from gatebench.config import ROOT
from gatebench.dataset import iter_papers, load_rows

GEMINI_DIR = "gemini-3.1-pro-preview-20260219"
GPT_DIR = "gpt-5.5-20260423"
OUT_PATH = ROOT / "reports" / "gemini_succeeds_gpt_fails.json"


def main():
    results = []

    for year, paper in iter_papers(GEMINI_DIR):
        gemini_rows = {r["question_number"]: r for r in load_rows(GEMINI_DIR, year, paper)}
        gpt_rows = {r["question_number"]: r for r in load_rows(GPT_DIR, year, paper)}

        for qnum, g_row in gemini_rows.items():
            if not g_row.get("has_image"):
                continue
            if g_row["is_correct"] is not True:
                continue
            gpt_row = gpt_rows.get(qnum)
            if gpt_row is None or gpt_row["is_correct"] is not False:
                continue

            results.append({
                "paper": paper,
                "question_number": qnum,
                "question": g_row["question"],
                "image": f"data/questions/{year}/images/{paper}/q{qnum}.png",
                "question_type": g_row["question_type"],
                "section": g_row["section"],
                "marks": g_row["marks"],
                "correct_answer": g_row["correct_answer"],
                "gemini_final_answer": g_row["final_answer"],
                "gemini_reasoning": g_row["reasoning"],
                "gemini_completion": g_row["completion"],
                "gpt_final_answer": gpt_row["final_answer"],
                "gpt_reasoning": gpt_row["reasoning"],
                "gpt_completion": gpt_row["completion"],
            })

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(results)} questions to {OUT_PATH}")


if __name__ == "__main__":
    main()
