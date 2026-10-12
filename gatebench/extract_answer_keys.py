"""
Deterministically extract GATE official answer keys from data/keys/<year>/<CODE>_Keys_<year>.pdf
into data/answer_keys/<year>/<CODE>_<year>.json, mirroring the layout of
data/questions/ produced by extract_questions.py.

The source PDFs are a single 6-column table (Q. No. / Session / Question Type
/ Section / Key or Range / Marks), rendered by PyMuPDF as one value per text
line. The table header repeats on every page (page-break artifact); that
repeat, the "Answer Key for ..." title, and "Page X of Y" footers are
stripped before the remaining lines are grouped into rows of 6.

Output per paper: a list of
    {"question_number": int, "session": int, "type": "MCQ"|"MSQ"|"NAT",
     "section": str, "answer": tuple|str, "marks": int|float}
"answer" is shaped by type (JSON has no tuple, so these serialize as
nested arrays): MCQ -> a 1-tuple of the option letter ("A",); MSQ -> a
tuple of option letters ("A","B","C"); NAT -> a tuple of (low, high) float
pairs -- one pair for a normal "<low> to <high>" range (equal endpoints for
an exact value), two pairs for the rarer case of a question with two
disjoint acceptable ranges ("<low1> to <high1> OR <low2> to <high2>", e.g.
a +/- answer). A voided question (marked "MTA*", "Marks To All") has no
real key regardless of its type, so it's kept as a bare string instead.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

from gatebench.config import KEYS_PDF_DIR as KEYS_DIR, ANSWER_KEYS_OUT_DIR as OUTPUT_DIR


HEADER_LABELS = ("Q. No.", "Session", "Q. Type", "Question Type", "Section", "Key/Range", "Marks")
TITLE_RE = re.compile(r"^Answer Key for .*$")
PAGE_OF_RE = re.compile(r"^Page\s*\d+\s*of\s*\d+$")
QTYPE_RE = re.compile(r"^(MCQ|MSQ|NAT)$")
NAT_RANGE_RE = re.compile(r"^(-?[\d.]+)\s+to\s+(-?[\d.]+)$")


def format_answer(qtype: str, raw: str):
    """MCQ -> 1-tuple of the option letter; MSQ -> tuple of option letters;
    NAT -> 2-tuple of (low, high) floats. A voided question (marked "MTA*",
    "Marks To All") has no real key regardless of type -- keep it as a bare
    string rather than forcing it into one of those shapes."""
    if raw.strip().upper().startswith("MTA"):
        return raw
    if qtype == "MCQ":
        return (raw,)
    if qtype == "MSQ":
        return tuple(opt.strip() for opt in raw.split(";"))
    if qtype == "NAT":
        # Usually one "<low> to <high>" range, but some answers (e.g. a
        # +/- value) give two disjoint acceptable ranges joined by " OR ".
        # Always return a tuple of (low, high) tuples so the shape is
        # consistent regardless of how many ranges there are.
        segments = []
        for part in raw.split(" OR "):
            m = NAT_RANGE_RE.match(part.strip())
            if not m:
                raise ValueError(f"NAT answer segment {part!r} (from {raw!r}) doesn't match '<low> to <high>'")
            segments.append((float(m.group(1)), float(m.group(2))))
        return tuple(segments)
    raise ValueError(f"unknown question type {qtype!r}")


def extract_lines(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        for raw_line in page.get_text().split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line in HEADER_LABELS or TITLE_RE.match(line) or PAGE_OF_RE.match(line):
                continue
            if line.startswith("*"):
                # Explanatory footnote, e.g. "*MTA= Marks To All" (a voided
                # question's row still carries a normal 6-field row with
                # "MTA*" as its answer -- only the standalone footnote line
                # itself needs stripping here).
                continue
            lines.append(line)
    doc.close()
    return lines


def parse_rows(lines: list[str]) -> list[dict]:
    if len(lines) % 6 != 0:
        raise ValueError(f"line count {len(lines)} is not a multiple of 6 -- unstripped boilerplate?")

    rows = []
    for i in range(0, len(lines), 6):
        qno, session, qtype, section, answer, marks = lines[i : i + 6]
        if not QTYPE_RE.match(qtype):
            raise ValueError(f"row {i // 6} has unexpected Q.Type {qtype!r} (row: {lines[i:i+6]!r})")
        try:
            marks_val = int(marks)
        except ValueError:
            marks_val = float(marks)
        rows.append(
            {
                "question_number": int(qno),
                "session": int(session),
                "type": qtype,
                "section": section,
                "answer": format_answer(qtype, answer),
                "marks": marks_val,
            }
        )
    return rows


def main():
    pdf_paths = sorted(KEYS_DIR.glob("*/*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {KEYS_DIR}", file=sys.stderr)
        sys.exit(1)

    for pdf_path in pdf_paths:
        lines = extract_lines(pdf_path)
        try:
            rows = parse_rows(lines)
        except ValueError as e:
            print(f"{pdf_path.relative_to(KEYS_DIR)}: FAILED -- {e}", file=sys.stderr)
            continue

        rel_dir = pdf_path.relative_to(KEYS_DIR).parent
        out_dir = OUTPUT_DIR / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # CS1_Keys_2025.pdf -> CS1_2025.json, matching data/questions/ naming.
        out_name = re.sub(r"_Keys", "", pdf_path.stem) + ".json"
        out_path = out_dir / out_name
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

        qnums = [r["question_number"] for r in rows]
        expected = list(range(1, len(rows) + 1))
        status = "OK" if qnums == expected else f"MISMATCH: question numbers not 1..{len(rows)} sequential"
        print(f"{pdf_path.relative_to(KEYS_DIR)}: {len(rows)} rows -> {out_path.relative_to(OUTPUT_DIR)} [{status}]")


if __name__ == "__main__":
    main()
