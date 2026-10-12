"""Shared paths, model/paper identifiers and display labels."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
PAPERS_PDF_DIR = DATA / "papers"
KEYS_PDF_DIR = DATA / "keys"
QUESTIONS_DIR = DATA / "questions"
ANSWER_KEYS_DIR = DATA / "answer_keys"
RESPONSES_DIR = DATA / "responses"
AIR1_PATH = DATA / "air1_scores.json"

RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
TABLES_DIR = ROOT / "tables"

# Where the extraction scripts WRITE. Set GATEBENCH_EXTRACT_OUT to redirect
# them somewhere other than data/, which is how `make extract` re-runs the
# pipeline and diffs the result without overwriting the committed, manually
# reviewed question bank. See the extraction caveat in the README.
_EXTRACT_OUT = os.environ.get("GATEBENCH_EXTRACT_OUT")
QUESTIONS_OUT_DIR = Path(_EXTRACT_OUT) / "questions" if _EXTRACT_OUT else QUESTIONS_DIR
ANSWER_KEYS_OUT_DIR = Path(_EXTRACT_OUT) / "answer_keys" if _EXTRACT_OUT else ANSWER_KEYS_DIR

# Directory name under data/responses/ -> short label used in every figure.
MODEL_DIR_LABELS = {
    "claude-4.7-opus-20260416": "CLAUDE",
    "gemini-3.1-pro-preview-20260219": "GEMINI",
    "gpt-5.5-20260423": "GPT",
    "grok-4.3-20260430": "GROK",
    "kimi-k2.6-20260420": "KIMI",
    "mistral-large-2512": "MISTRAL",
    "qwen3.6-plus-04-02": "QWEN",
}

# OpenRouter slug -> directory name, for run_benchmark.py.
MODEL_SLUGS = {
    "anthropic/claude-4.7-opus-20260416": "claude-4.7-opus-20260416",
    "google/gemini-3.1-pro-preview-20260219": "gemini-3.1-pro-preview-20260219",
    "openai/gpt-5.5-20260423": "gpt-5.5-20260423",
    "x-ai/grok-4.3-20260430": "grok-4.3-20260430",
    "moonshotai/kimi-k2.6-20260420": "kimi-k2.6-20260420",
    "mistralai/mistral-large-2512": "mistral-large-2512",
    "qwen/qwen3.6-plus-04-02": "qwen3.6-plus-04-02",
}

MODELS = ["CLAUDE", "GEMINI", "GPT", "GROK", "KIMI", "MISTRAL", "QWEN"]
PAPERS = ["CS1", "CS2", "DA", "EC", "EE", "MA"]
YEARS = ["2025", "2026"]

# Questions per paper, and the prescribed exam duration used as the
# reference line in the generation-time comparison.
QUESTIONS_PER_PAPER = 65
EXAM_DURATION_MIN = 180
