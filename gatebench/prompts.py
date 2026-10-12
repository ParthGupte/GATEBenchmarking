"""
The exact prompt used for every query in the benchmark.

Reproduced verbatim: the answer-format rules below are what make a response
machine-scorable, so altering this string makes a re-run incomparable with the
published results.
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "\nYou are solving a GATE exam question.\n\n"
    "Give a clear step-by-step solution.\n\n"
    "At the VERY END, you MUST output the final answer in EXACTLY this format:\n\n"
    "FINAL_ANSWER: <answer>\n\n"
    "Rules:\n"
    "- MCQ: output A/B/C/D\n"
    "- MSQ: output A,B,C\n"
    "- NAT: output number only\n"
)


def build_messages(question_text: str, image_b64: str | None) -> list[dict]:
    """Chat messages for one question.

    A text-only question sends ``content`` as a bare string while an image
    question sends a two-element list; both shapes are what the benchmark
    actually sent, so neither is normalised to the other.
    """
    if image_b64:
        user_content = [
            {"type": "text", "text": question_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
            },
        ]
    else:
        user_content = question_text
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
