"""
Joined read access to the benchmark data.

The dataset is stored in two halves: data/responses/ holds what each model
said (reasoning, completion, final answer) and results/ holds how it was
marked. They share question_number. Analysis that needs both -- reading a
model's reasoning alongside whether it was right -- goes through here.
"""

from __future__ import annotations

import json

from gatebench.config import MODEL_DIR_LABELS, RESPONSES_DIR, RESULTS_DIR


def model_dirs() -> list[str]:
    return sorted(d.name for d in RESPONSES_DIR.iterdir()
                  if d.is_dir() and d.name in MODEL_DIR_LABELS)


def load_rows(model_dir: str, year: str, paper_stem: str) -> list[dict]:
    """One merged row per question, carrying both the model's text and its
    marking outcome. Ordered by question_number."""
    resp_path = RESPONSES_DIR / model_dir / year / f"{paper_stem}.json"
    res_path = RESULTS_DIR / model_dir / year / f"{paper_stem}.json"

    responses = json.load(open(resp_path))
    graded = {r["question_number"]: r for r in json.load(open(res_path))}

    merged = []
    for r in responses:
        g = graded.get(r["question_number"], {})
        row = dict(r)
        row.update({k: v for k, v in g.items() if k != "question_number"})
        merged.append(row)
    return merged


def iter_papers(model_dir: str):
    """Yield (year, paper_stem) for every paper this model has, in order."""
    root = RESPONSES_DIR / model_dir
    for path in sorted(root.glob("*/*.json")):
        yield path.parent.name, path.stem
