"""
Deterministically extract question numbers and question text (including
options) from GATE question paper PDFs.

For each PDF under data/papers/<year>/<CODE>_<year>.pdf this writes a JSON file
data/questions/<year>/<CODE>_<year>.json (mirroring the data/papers/ layout)
containing a list of:

    {"question_number": int, "question": str, "image_url": None}

`image_url` is a placeholder for now; it will be filled in by a later pass
that locates and encodes per-question figures.

Approach
--------
GATE papers repeat the same boilerplate (subject title, "Organising/
Organizing Institute: ...", "Page X of Y", "GATE <year>") on every page, and
sandwich each section with a "Q.a - Q.b carry ... mark(s) each" header. Both
are stripped before splitting the remaining text on question markers
("Q.<n>" / "Q. <n>"), since the range headers themselves contain "Q.<n>"
substrings that would otherwise be mistaken for question boundaries.

Boilerplate lines are detected by frequency (a line repeated on a large
fraction of pages is page furniture, not question content) rather than
hardcoded per subject, since title formatting/ligatures vary between papers.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from gatebench.config import PAPERS_PDF_DIR as PAPERS_DIR, QUESTIONS_OUT_DIR as OUTPUT_DIR


SECTION_HEADER_RE = re.compile(
    r"Q\.\s*\d+[A-Za-z]?\s*[–‒\-]\s*Q\.\s*\d+[A-Za-z]?\s*carry\s+(one|two)\s+marks?\s+(each|only)\.?",
    re.IGNORECASE,
)
INSTITUTE_LINE_RE = re.compile(r"Organi[sz]ing Institute:[^\n]*")
PAGE_OF_RE = re.compile(r"Page\s*\d+\s*of\s*\d+")
GATE_YEAR_RE = re.compile(r"\bGATE\s*20\d{2}\b")
GENERAL_APTITUDE_RE = re.compile(r"^General Aptitude\s*$", re.MULTILINE)
EXTRA_BUFFER_HEADING_RE = re.compile(r"EXTRA\s*\(BUFFER\)\s*Questions", re.IGNORECASE)

# Normal questions are "Q.<n>"; a small number of papers (e.g. GATE 2025 EE)
# append "EXTRA (BUFFER)" questions labelled "Q.<n><letter>" (Q.1A, Q.1B, ...)
# after the main Q.65. Capture the optional letter so these still act as
# split boundaries instead of corrupting the preceding real question.
QUESTION_MARKER_RE = re.compile(r"Q\.\s*(\d+)([A-Za-z])?\b")

BOILERPLATE_FREQ_THRESHOLD = 0.1


def strip_known_boilerplate(text: str) -> str:
    text = SECTION_HEADER_RE.sub(" ", text)
    text = INSTITUTE_LINE_RE.sub(" ", text)
    text = PAGE_OF_RE.sub(" ", text)
    text = GATE_YEAR_RE.sub(" ", text)
    text = GENERAL_APTITUDE_RE.sub(" ", text)
    text = EXTRA_BUFFER_HEADING_RE.sub(" ", text)
    return text


def strip_repeated_lines(page_texts: list[str]) -> list[str]:
    """Drop lines that recur near-verbatim across a large fraction of pages
    (subject title banners etc.) -- these vary by subject/paper, so they
    can't be hardcoded, but they show up on almost every page."""
    line_counts = Counter()
    for text in page_texts:
        seen_this_page = set()
        for line in text.split("\n"):
            stripped = line.strip()
            # Short lines ("(A)", "42", "Yes") are common option labels/
            # answers, not page furniture -- never flag them as boilerplate
            # no matter how often they recur.
            if not stripped or len(stripped) < 10 or QUESTION_MARKER_RE.match(stripped):
                continue
            if stripped not in seen_this_page:
                line_counts[stripped] += 1
                seen_this_page.add(stripped)

    n_pages = len(page_texts)
    boilerplate = {
        line
        for line, count in line_counts.items()
        if count >= max(3, n_pages * BOILERPLATE_FREQ_THRESHOLD)
    }

    cleaned = []
    for text in page_texts:
        kept_lines = [
            line for line in text.split("\n") if line.strip() not in boilerplate
        ]
        cleaned.append("\n".join(kept_lines))
    return cleaned


def split_into_questions(full_text: str) -> tuple[dict[int, str], list[tuple[str, str]]]:
    """Returns (normal, extra): normal maps question number -> text for
    plain "Q.<n>" markers; extra is an ordered list of (label, text) for
    lettered "Q.<n><letter>" bonus/buffer questions (rare -- see GATE 2025
    EE's "EXTRA (BUFFER) Questions" section)."""
    matches = list(QUESTION_MARKER_RE.finditer(full_text))
    normal: dict[int, str] = {}
    extra: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        base = int(m.group(1))
        letter = m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        body = re.sub(r"\n{2,}", "\n", body)
        body = re.sub(r"[ \t]+", " ", body)
        body = "\n".join(line.strip() for line in body.split("\n")).strip()
        if not body:
            continue
        if letter:
            extra.append((f"{base}{letter}", body))
        # Keep the first occurrence's worth of content; later duplicate
        # markers for the same number (shouldn't happen once boilerplate is
        # stripped) are ignored rather than overwriting good content.
        elif base not in normal:
            normal[base] = body
    return normal, extra


def extract_pdf(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    page_texts = [page.get_text() for page in doc]
    doc.close()

    page_texts = [strip_known_boilerplate(t) for t in page_texts]
    page_texts = strip_repeated_lines(page_texts)

    full_text = "\n".join(page_texts)
    normal, extra = split_into_questions(full_text)

    result = []
    for qnum in sorted(normal):
        result.append(
            {
                "question_number": qnum,
                "question": normal[qnum],
                "image_url": None,
            }
        )

    # Lettered bonus/buffer questions (e.g. GATE 2025 EE's "EXTRA (BUFFER)
    # Questions" Q.1A-Q.1E, Q.2A-Q.2E) aren't part of the normal Q.1-Q.65
    # sequence. Keep them, numbered continuing on from the highest normal
    # question, with their original label preserved in the text so nothing
    # is silently dropped.
    next_num = (max(normal) if normal else 0) + 1
    for label, body in extra:
        result.append(
            {
                "question_number": next_num,
                "question": f"[Extra buffer question, labelled Q.{label} in source PDF]\n{body}",
                "image_url": None,
            }
        )
        next_num += 1

    return result


def main():
    pdf_paths = sorted(PAPERS_DIR.glob("*/*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {PAPERS_DIR}", file=sys.stderr)
        sys.exit(1)

    for pdf_path in pdf_paths:
        questions = extract_pdf(pdf_path)
        rel_dir = pdf_path.relative_to(PAPERS_DIR).parent
        out_dir = OUTPUT_DIR / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / pdf_path.with_suffix(".json").name
        with open(out_path, "w") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        expected = set(range(1, 66))
        found = {q["question_number"] for q in questions}
        missing = sorted(expected - found)
        bonus = sorted(found - expected)
        if missing:
            status = f"MISMATCH missing={missing}"
        elif bonus:
            status = f"OK (+{len(bonus)} extra/buffer questions numbered {bonus})"
        else:
            status = "OK"
        print(f"{pdf_path.relative_to(PAPERS_DIR)}: {len(questions)} questions -> {out_path.name} [{status}]")


if __name__ == "__main__":
    main()
