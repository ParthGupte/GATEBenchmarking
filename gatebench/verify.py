"""
Self-check for the committed dataset and the extraction pipeline.

Two independent things are verified:

1. Dataset invariants over data/responses/ and results/ -- row counts,
   coverage gaps, marking outcomes. These catch a corrupted or partial
   checkout, and a scoring change that silently moves a published number.

2. Extraction reproducibility. The PDFs are re-parsed into a scratch
   directory and compared against the committed bank. Question text and
   answer keys must match exactly. Image attachment is expected NOT to
   match: it is a heuristic that over-attaches, and the committed bank
   reflects manual review (see the README).

Run:  python -m gatebench.verify
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from gatebench.config import (
    ANSWER_KEYS_DIR, PAPERS, QUESTIONS_DIR, RESPONSES_DIR, RESULTS_DIR,
)

EXPECTED = {
    "total rows": 5530,
    "buffer rows": 70,
    "scored rows": 5460,
    "null final_answer": 11,
    "MTA rows": 14,
    "image rows (all)": 1064,
    "image rows (scored)": 1050,
    "section GA": 840,
    "type MCQ": 3003,
    "type NAT": 1323,
    "type MSQ": 1134,
}


def check_dataset() -> bool:
    rows = buffer = nulls = mta = img_all = img_scored = 0
    sections, qtypes = Counter(), Counter()
    nulls_by_model = Counter()

    result_files = sorted(RESULTS_DIR.glob("*/*/*.json"))
    if not result_files:
        print("  no results/ found -- run `python -m gatebench.score` first")
        return False

    for path in result_files:
        model_dir = path.parts[-3]
        resp = RESPONSES_DIR / model_dir / path.parts[-2] / path.name
        if not resp.exists():
            print(f"  missing responses file for {path}")
            return False
        for r in json.load(open(path)):
            rows += 1
            if r["has_image"]:
                img_all += 1
            if r["question_type"] is None:
                buffer += 1
                continue
            if r["has_image"]:
                img_scored += 1
            if r["final_answer"] is None:
                nulls += 1
                nulls_by_model[model_dir] += 1
            ca = r["correct_answer"]
            if isinstance(ca, str) and ca.upper().startswith("MTA"):
                mta += 1
            sections[r["section"]] += 1
            qtypes[r["question_type"]] += 1

    got = {
        "total rows": rows,
        "buffer rows": buffer,
        "scored rows": rows - buffer,
        "null final_answer": nulls,
        "MTA rows": mta,
        "image rows (all)": img_all,
        "image rows (scored)": img_scored,
        "section GA": sections["GA"],
        "type MCQ": qtypes["MCQ"],
        "type NAT": qtypes["NAT"],
        "type MSQ": qtypes["MSQ"],
    }

    ok = True
    for name, want in EXPECTED.items():
        flag = "ok  " if got[name] == want else "FAIL"
        if got[name] != want:
            ok = False
        print(f"  [{flag}] {name:22s} {got[name]:6d}  (expect {want})")
    print(f"         unanswered by model: {dict(nulls_by_model)}")
    return ok


def check_extraction() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="gatebench-extract-"))
    try:
        env_prefix = {"GATEBENCH_EXTRACT_OUT": str(tmp)}
        import os
        env = {**os.environ, **env_prefix}
        for mod in ("gatebench.extract_answer_keys",
                    "gatebench.extract_questions",
                    "gatebench.extract_images"):
            proc = subprocess.run([sys.executable, "-m", mod], env=env,
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"  [FAIL] {mod} exited {proc.returncode}")
                print(proc.stderr[-800:])
                return False

        text_mismatch = key_mismatch = 0
        committed_imgs = regenerated_imgs = 0
        for committed in sorted(QUESTIONS_DIR.glob("*/*.json")):
            regen = tmp / "questions" / committed.parent.name / committed.name
            c, r = json.load(open(committed)), json.load(open(regen))
            text_mismatch += sum(1 for a, b in zip(c, r) if a["question"] != b["question"])
            committed_imgs += sum(1 for q in c if q.get("image_url"))
            regenerated_imgs += sum(1 for q in r if q.get("image_url"))
        for committed in sorted(ANSWER_KEYS_DIR.glob("*/*.json")):
            regen = tmp / "answer_keys" / committed.parent.name / committed.name
            if json.load(open(committed)) != json.load(open(regen)):
                key_mismatch += 1

        ok = text_mismatch == 0 and key_mismatch == 0
        print(f"  [{'ok  ' if text_mismatch == 0 else 'FAIL'}] question text mismatches  {text_mismatch}")
        print(f"  [{'ok  ' if key_mismatch == 0 else 'FAIL'}] answer-key file mismatches {key_mismatch}")
        print(f"  [note] image attachment: {committed_imgs} committed vs "
              f"{regenerated_imgs} auto-detected -- the committed bank is "
              f"manually reviewed, so a difference here is expected")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    print("Dataset invariants")
    data_ok = check_dataset()
    print("\nExtraction reproducibility (re-parses the PDFs; takes a minute)")
    extract_ok = check_extraction()
    print("\n" + ("ALL CHECKS PASSED" if (data_ok and extract_ok) else "*** CHECKS FAILED ***"))
    sys.exit(0 if (data_ok and extract_ok) else 1)


if __name__ == "__main__":
    main()
