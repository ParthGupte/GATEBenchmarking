"""
Grade every model response against the official answer keys.

Reads  data/responses/<model>/<year>/<PAPER>_<year>.json
       data/answer_keys/<year>/<PAPER>_<year>.json
Writes results/<model>/<year>/<PAPER>_<year>.json

The output carries one row per question with the marking outcome but without
the bulky reasoning/completion text, so every figure and table can be built
from results/ alone. Join back to data/responses/ on question_number to read
what a model actually said.

Marking rules live in gatebench.scoring.

Run:  python -m gatebench.score
"""

from __future__ import annotations

import json
from pathlib import Path

from gatebench.config import ANSWER_KEYS_DIR, RESPONSES_DIR, RESULTS_DIR
from gatebench.scoring import compute_marks_obtained, is_voided, score


def load_keys() -> dict[str, dict[int, dict]]:
    index = {}
    for path in sorted(ANSWER_KEYS_DIR.glob("*/*.json")):
        rows = json.load(open(path))
        index[path.stem] = {row["question_number"]: row for row in rows}
    return index


def grade_paper(rows: list[dict], key_index: dict[int, dict]) -> list[dict]:
    out = []
    for r in rows:
        qnum = r["question_number"]
        key = key_index.get(qnum)

        if key is None:
            # Buffer question with no official key (EE 2025 #66-75). Every
            # key-derived field stays null; downstream analysis skips these
            # on question_type being None.
            out.append({
                "question_number": qnum,
                "question_type": None,
                "section": None,
                "marks": None,
                "has_image": r["has_image"],
                "correct_answer": None,
                "final_answer": None,
                "is_correct": None,
                "marks_obtained": None,
                "generation_time_s": r.get("generation_time_s"),
                "generation_cost": r.get("generation_cost"),
            })
            continue

        qtype = key["type"]
        marks = key["marks"]
        final_answer = r.get("final_answer")

        if is_voided(key["answer"]):
            is_correct = None
            marks_obtained = marks
        else:
            is_correct = score(qtype, final_answer, key["answer"])
            marks_obtained = compute_marks_obtained(qtype, marks, is_correct)

        out.append({
            "question_number": qnum,
            "question_type": qtype,
            "section": key["section"],
            "marks": marks,
            "has_image": r["has_image"],
            "correct_answer": key["answer"],
            "final_answer": final_answer,
            "is_correct": is_correct,
            "marks_obtained": marks_obtained,
            "generation_time_s": r.get("generation_time_s"),
            "generation_cost": r.get("generation_cost"),
        })
    return out


def main() -> None:
    keys = load_keys()
    written = rows_total = 0

    for src in sorted(RESPONSES_DIR.glob("*/*/*.json")):
        model_dir, year, fname = src.parts[-3], src.parts[-2], src.parts[-1]
        paper = Path(fname).stem
        rows = json.load(open(src))

        graded = grade_paper(rows, keys.get(paper, {}))
        dst = RESULTS_DIR / model_dir / year / fname
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w") as f:
            json.dump(graded, f, indent=2, ensure_ascii=False)

        written += 1
        rows_total += len(graded)

    print(f"Graded {rows_total} rows into {written} files under {RESULTS_DIR}")


if __name__ == "__main__":
    main()
