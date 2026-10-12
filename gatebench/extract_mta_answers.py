"""
Dump every model's final_answer, reasoning, and completion on MTA (voided,
"Marks To All") questions into a single JSON file -- one dictionary per
question, with a nested per-model answer breakdown.
"""

import glob
import json
from pathlib import Path

from gatebench.config import ANSWER_KEYS_DIR, ROOT
from gatebench.dataset import load_rows, model_dirs as all_model_dirs

KEYS_GLOB = str(ANSWER_KEYS_DIR / "*" / "*.json")
OUT_PATH = ROOT / "reports" / "mta_question_answers.json"


def find_mta_questions():
    """Yield (paper, question_number) for every voided question."""
    for path in glob.glob(KEYS_GLOB):
        paper = Path(path).stem
        for row in json.load(open(path)):
            answer = row["answer"]
            if isinstance(answer, str) and answer.upper().startswith("MTA"):
                yield paper, row["question_number"]


def main():
    model_dirs = all_model_dirs()
    results = []

    for paper, qnum in find_mta_questions():
        year = paper.rsplit("_", 1)[-1]
        entry = None
        model_answers = {}

        for model_dir in model_dirs:
            rows = {r["question_number"]: r for r in load_rows(model_dir, year, paper)}
            row = rows[qnum]
            if entry is None:
                entry = {
                    "paper": paper,
                    "question_number": qnum,
                    "question": row["question"],
                    "image": (f"data/questions/{year}/images/{paper}/q{qnum}.png"
                              if row.get("has_image") else None),
                    "question_type": row["question_type"],
                    "section": row["section"],
                    "marks": row["marks"],
                }
            model_answers[model_dir] = {
                "final_answer": row["final_answer"],
                "reasoning": row["reasoning"],
                "completion": row["completion"],
            }

        entry["model_answers"] = model_answers
        results.append(entry)

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(results)} MTA questions to {OUT_PATH}")


if __name__ == "__main__":
    main()
