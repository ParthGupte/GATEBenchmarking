"""
Official GATE marking scheme.

The three functions here determine every accuracy and marks figure in the
paper, so they are kept exactly as they were when the published results were
computed. The rules:

  - MCQ: correct -> full marks. A wrong-but-valid-option answer -> official
    GATE negative marking, -marks/3. Unattempted or unparseable/blank ->
    null for both is_correct and marks_obtained (a genuine wrong pick cannot
    be distinguished from a parsing gap, so no credit either way).
  - MSQ / NAT: correct -> full marks; wrong (valid but incorrect) -> 0 (GATE
    applies no negative marking here); unattempted/unparseable -> null/null.
  - Voided (MTA, "Marks To All") questions: every model gets full marks
    regardless of attempt or answer, matching the official policy.
    is_correct is null -- correctness is not meaningful for a voided question.
  - Buffer questions with no official answer key (EE 2025 #66-75) get null
    for every key-derived field and are excluded from all analysis.
"""

from __future__ import annotations


def is_voided(key_answer) -> bool:
    """True for questions the official key voided ("Marks To All")."""
    return isinstance(key_answer, str) and key_answer.upper().startswith("MTA")


def score(qtype: str, final_answer: str | None, key_answer) -> bool | None:
    """Correct / incorrect / unscorable (None) for one answer."""
    if final_answer is None:
        return None
    fa = final_answer.strip().upper().rstrip(".")
    try:
        if qtype == "MCQ":
            if fa not in ("A", "B", "C", "D"):
                return None
            return fa == key_answer[0]
        if qtype == "MSQ":
            letters = {x.strip() for x in fa.replace(" ", "").split(",")}
            if not letters or not letters.issubset({"A", "B", "C", "D"}):
                return None
            return letters == set(key_answer)
        if qtype == "NAT":
            val = float(fa)
            # NAT keys are tolerance ranges, and a few questions carry two
            # acceptable ranges -- any match counts.
            return any(lo <= val <= hi for lo, hi in key_answer)
    except (ValueError, IndexError, TypeError):
        return None
    return None


def compute_marks_obtained(qtype: str, marks, is_correct: bool | None):
    """GATE marks awarded, including MCQ negative marking."""
    if is_correct is None:
        return None
    if is_correct:
        return marks
    if qtype == "MCQ":
        return round(-marks / 3, 2)
    return 0
