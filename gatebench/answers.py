"""
Parsing of the ``FINAL_ANSWER:`` line that every benchmark prompt asks the
model to emit (see :mod:`gatebench.prompts`).

This is deliberately forgiving. Models wrap the line in markdown, quote the
instruction back to themselves mid-reasoning, or close the bold markup right
after the colon and put the answer on the next line. Each of those quirks was
observed in the benchmark run and is handled below; the behaviour here decides
which string reaches scoring, so changing it changes published results.
"""

from __future__ import annotations

import re

FINAL_ANSWER_RE = re.compile(r"FINAL_ANSWER:\s*(.+)")


def _clean_answer_candidate(raw: str) -> str:
    # Some models wrap the whole "FINAL_ANSWER: X" line in markdown bold
    # (e.g. "**FINAL_ANSWER: B**"), which leaves a trailing "**" glued onto
    # the captured value ("B**") -- strip it so downstream scoring sees a
    # clean "B" instead of silently failing to parse it as any of A/B/C/D.
    return raw.strip().strip("*").strip()


def extract_final_answer(completion: str | None, reasoning: str | None) -> str | None:
    """Recover the model's final answer, preferring the completion over the
    reasoning trace. Returns ``None`` when no usable answer was stated."""
    for text in (completion, reasoning):
        if not text:
            continue
        candidates = []
        # The model's own reasoning often quotes the system prompt's output
        # format instructions verbatim while thinking about how to answer
        # (e.g. "The instruction says ... FINAL_ANSWER: <answer> Rules: ...").
        # That's a literal template echo, not a real answer -- skip matches
        # whose captured group is the placeholder itself, and prefer the
        # LAST match (the real answer statement comes at the end).
        for mo in FINAL_ANSWER_RE.finditer(text):
            candidate = _clean_answer_candidate(mo.group(1))
            if not candidate:
                # The bold markup sometimes closes right after the colon,
                # pushing the actual answer onto the next line entirely
                # (e.g. "**FINAL_ANSWER:**\n0.6, 1.2") -- fall back to the
                # next non-blank line in that case.
                for line in text[mo.end():].splitlines():
                    line = _clean_answer_candidate(line)
                    if line:
                        candidate = line
                        break
            if candidate and not candidate.startswith("<answer>"):
                candidates.append(candidate)
        if candidates:
            return candidates[-1]
    return None
