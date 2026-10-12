"""
Query the models through the OpenRouter chat-completions API.

This is the data-collection step. It is how the committed responses were
produced, and re-running it re-collects them -- but note that model sampling
is non-deterministic and providers update models behind a slug, so a fresh
run yields NEW generations rather than reproducing the committed files. Treat
a re-run as an independent replication, not a bit-for-bit rebuild.

Each (model, paper, question) that is not already present in
data/responses/ is queried once. Answers stream into a per-paper .jsonl
alongside the final JSON (concurrent writers would otherwise collide), and
--consolidate folds them into the committed layout.

THIS COSTS REAL MONEY. A full sweep of all 7 models x 12 papers x 65
questions is roughly $60 at the per-question averages in Table I. The script
refuses to make paid calls without --yes, and --dry-run needs no API key.

Usage:
    export OPENROUTER_API_KEY=sk-or-v1-...
    python -m gatebench.run_benchmark --dry-run --limit 3
    python -m gatebench.run_benchmark --limit 3 --yes
    python -m gatebench.run_benchmark --yes
    python -m gatebench.run_benchmark --consolidate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from gatebench.answers import extract_final_answer
from gatebench.config import (
    ANSWER_KEYS_DIR, MODEL_SLUGS, QUESTIONS_DIR, RESPONSES_DIR,
)
from gatebench.prompts import build_messages

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BACKOFF_SCHEDULE = (5.0, 20.0, 60.0)

# Rough per-question cost used only for the pre-flight estimate.
AVG_COST_PER_MODEL = {
    "anthropic/claude-4.7-opus-20260416": 0.0122,
    "google/gemini-3.1-pro-preview-20260219": 0.0570,
    "mistralai/mistral-large-2512": 0.0017,
    "moonshotai/kimi-k2.6-20260420": 0.0294,
    "openai/gpt-5.5-20260423": 0.0333,
    "qwen/qwen3.6-plus-04-02": 0.0213,
    "x-ai/grok-4.3-20260430": 0.0059,
}


# --------------------------------------------------------------------------
# worklist
# --------------------------------------------------------------------------

def load_question_bank() -> dict[tuple[str, int], dict]:
    bank = {}
    for path in sorted(QUESTIONS_DIR.glob("*/*.json")):
        paper = path.stem
        for q in json.load(open(path)):
            bank[(paper, q["question_number"])] = q
    return bank


def load_keyed_universe() -> dict[str, set[int]]:
    """Questions that have an official answer key -- buffer questions are
    excluded from the benchmark, so they are never queried."""
    universe = {}
    for path in sorted(ANSWER_KEYS_DIR.glob("*/*.json")):
        universe[path.stem] = {row["question_number"] for row in json.load(open(path))}
    return universe


def existing_coverage(model_dir: str) -> dict[str, set[int]]:
    covered = {}
    root = RESPONSES_DIR / model_dir
    if not root.exists():
        return covered
    for path in sorted(root.glob("*/*.json")):
        answered = {r["question_number"] for r in json.load(open(path))
                    if r.get("final_answer") is not None}
        covered[path.stem] = answered
    for path in sorted(root.glob("*/*.jsonl")):
        answered = covered.setdefault(path.stem, set())
        with open(path) as f:
            for line in f:
                if line.strip():
                    answered.add(json.loads(line)["question_number"])
    return covered


def compute_worklist(slugs: list[str]) -> list[tuple[str, str, int]]:
    universe = load_keyed_universe()
    worklist = []
    for slug in slugs:
        model_dir = MODEL_SLUGS[slug]
        covered = existing_coverage(model_dir)
        for paper, qnums in sorted(universe.items()):
            done = covered.get(paper, set())
            for qnum in sorted(qnums):
                if qnum not in done:
                    worklist.append((slug, paper, qnum))
    return worklist


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def build_payload(model: str, messages: list[dict]) -> dict:
    return {"model": model, "messages": messages, "usage": {"include": True}}


def extract_reasoning(message: dict) -> str | None:
    reasoning = message.get("reasoning")
    if reasoning:
        return reasoning
    details = message.get("reasoning_details")
    if details:
        parts = [d.get("text") or d.get("summary") for d in details]
        parts = [p for p in parts if p]
        if parts:
            return "\n".join(parts)
    return message.get("reasoning_content")


def extract_completion(message: dict) -> str | None:
    content = message.get("content")
    if isinstance(content, list):
        parts = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
        return "\n".join(parts) if parts else None
    return content


def parse_response(raw: dict, qnum: int, question_text: str, has_image: bool,
                   elapsed_s: float) -> dict:
    choice = raw["choices"][0]
    message = choice.get("message", {})
    usage = raw.get("usage", {}) or {}

    completion = extract_completion(message)
    reasoning = extract_reasoning(message)

    return {
        "question_number": qnum,
        "question": question_text,
        "has_image": has_image,
        "reasoning": reasoning,
        "completion": completion,
        "final_answer": extract_final_answer(completion, reasoning),
        "generation_time_s": elapsed_s,
        "generation_cost": usage.get("cost"),
        "tokens_prompt": usage.get("prompt_tokens"),
        "tokens_completion": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
    }


class NonRetryableError(Exception):
    pass


async def call_once(client: httpx.AsyncClient, api_key: str, payload: dict) -> dict:
    resp = await client.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
    )
    if resp.status_code in RETRYABLE_STATUS:
        resp.raise_for_status()
    if resp.status_code >= 400:
        raise NonRetryableError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json()


async def call_with_retries(client: httpx.AsyncClient, api_key: str, payload: dict) -> dict:
    last_exc = None
    for attempt in range(len(BACKOFF_SCHEDULE) + 1):
        try:
            return await call_once(client, api_key, payload)
        except NonRetryableError:
            raise
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
            last_exc = e
            if attempt < len(BACKOFF_SCHEDULE):
                delay = BACKOFF_SCHEDULE[attempt] * (1 + random.uniform(-0.2, 0.2))
                await asyncio.sleep(delay)
    raise last_exc


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

class Stats:
    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.succeeded = 0
        self.failed_items: list[tuple[str, str, int, str]] = []
        self.total_cost = 0.0
        self.lock = asyncio.Lock()
        self.start = time.monotonic()

    async def record_success(self, model, paper, qnum, cost, elapsed):
        async with self.lock:
            self.done += 1
            self.succeeded += 1
            self.total_cost += cost or 0.0
            print(f"[{self.done}/{self.total}] {model} {paper}#{qnum} ok "
                  f"cost=${cost or 0:.4f} elapsed={elapsed:.1f}s "
                  f"(running total: ${self.total_cost:.2f})", file=sys.stderr)

    async def record_failure(self, model, paper, qnum, reason):
        async with self.lock:
            self.done += 1
            self.failed_items.append((model, paper, qnum, reason))
            print(f"[{self.done}/{self.total}] {model} {paper}#{qnum} FAILED: {reason} "
                  f"(running total: ${self.total_cost:.2f})", file=sys.stderr)

    def print_summary(self):
        elapsed = time.monotonic() - self.start
        print("\n=== Summary ===", file=sys.stderr)
        print(f"Attempted: {self.done}/{self.total}", file=sys.stderr)
        print(f"Succeeded: {self.succeeded}", file=sys.stderr)
        print(f"Failed: {len(self.failed_items)}", file=sys.stderr)
        print(f"Total cost: ${self.total_cost:.2f}", file=sys.stderr)
        print(f"Wall-clock: {elapsed:.1f}s", file=sys.stderr)
        if self.failed_items:
            print("Failed triples (retried automatically on the next run):", file=sys.stderr)
            for model, paper, qnum, reason in self.failed_items:
                print(f"  {model} {paper}#{qnum}: {reason}", file=sys.stderr)
        print("\nRun with --consolidate to fold the .jsonl output into "
              "data/responses/, then `python -m gatebench.score`.", file=sys.stderr)


def jsonl_path(slug: str, paper: str) -> Path:
    year = paper.rsplit("_", 1)[-1]
    return RESPONSES_DIR / MODEL_SLUGS[slug] / year / f"{paper}.jsonl"


async def process_pair(client, api_key, sem, file_locks, slug, paper, qnum,
                       question_row, stats):
    image_b64 = question_row.get("image_url")
    messages = build_messages(question_row["question"], image_b64)
    payload = build_payload(slug, messages)
    start = time.monotonic()
    async with sem:
        try:
            raw = await call_with_retries(client, api_key, payload)
        except Exception as e:
            await stats.record_failure(slug, paper, qnum, str(e))
            return
    elapsed = time.monotonic() - start

    try:
        entry = parse_response(raw, qnum, question_row["question"],
                               bool(image_b64), elapsed)
    except (KeyError, IndexError) as e:
        await stats.record_failure(slug, paper, qnum, f"malformed response: {e}")
        return

    path = jsonl_path(slug, paper)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = file_locks.setdefault(path, asyncio.Lock())
    async with lock:
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    await stats.record_success(slug, paper, qnum, entry["generation_cost"], elapsed)


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit(
            "OPENROUTER_API_KEY is not set. Export it before running, e.g.\n"
            "  export OPENROUTER_API_KEY=sk-or-v1-...\n"
            "(get a key from https://openrouter.ai/settings/keys)"
        )
    return key


async def run(worklist, question_bank, concurrency: int, timeout: float):
    api_key = get_api_key()
    stats = Stats(len(worklist))
    sem = asyncio.Semaphore(concurrency)
    file_locks: dict[Path, asyncio.Lock] = {}
    timeout_cfg = httpx.Timeout(connect=15.0, read=timeout, write=30.0, pool=None)
    async with httpx.AsyncClient(timeout=timeout_cfg) as client:
        await asyncio.gather(*[
            process_pair(client, api_key, sem, file_locks, slug, paper, qnum,
                         question_bank[(paper, qnum)], stats)
            for slug, paper, qnum in worklist
        ])
    stats.print_summary()


def consolidate() -> None:
    """Fold any .jsonl run output into the committed per-paper JSON."""
    merged = 0
    for jl in sorted(RESPONSES_DIR.glob("*/*/*.jsonl")):
        target = jl.with_suffix(".json")
        rows = {}
        if target.exists():
            rows = {r["question_number"]: r for r in json.load(open(target))}
        with open(jl) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    rows[r["question_number"]] = r
        ordered = [rows[k] for k in sorted(rows)]
        with open(target, "w") as f:
            json.dump(ordered, f, indent=2, ensure_ascii=False)
        jl.unlink()
        merged += 1
        print(f"consolidated {jl.name} -> {target.name} ({len(ordered)} rows)")
    print(f"Done. {merged} file(s) merged." if merged else "Nothing to consolidate.")


def print_dry_run(worklist, question_bank) -> None:
    for slug, paper, qnum in worklist:
        row = question_bank[(paper, qnum)]
        note = f" +image({len(row['image_url'])} b64 chars)" if row.get("image_url") else ""
        print(f"{slug} {paper}#{qnum}: {len(row['question'])} chars{note}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the worklist, make no network calls, no API key needed.")
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N items.")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=600.0, help="Per-request read timeout (s).")
    ap.add_argument("--models", type=str, default=None,
                    help="Comma-separated subset of model slugs.")
    ap.add_argument("--yes", action="store_true",
                    help="Required to actually make real (paid) API calls.")
    ap.add_argument("--consolidate", action="store_true",
                    help="Merge .jsonl run output into data/responses/ and exit.")
    args = ap.parse_args()

    if args.consolidate:
        consolidate()
        return

    slugs = args.models.split(",") if args.models else list(MODEL_SLUGS)
    unknown = [s for s in slugs if s not in MODEL_SLUGS]
    if unknown:
        sys.exit(f"Unknown model slug(s): {unknown}\nKnown: {list(MODEL_SLUGS)}")

    question_bank = load_question_bank()
    worklist = compute_worklist(slugs)
    if args.limit:
        worklist = worklist[: args.limit]

    if not worklist:
        print("Nothing to do -- every keyed question already has an answer.", file=sys.stderr)
        return

    est = sum(AVG_COST_PER_MODEL.get(slug, 0.02) for slug, _, _ in worklist)
    print(f"Worklist: {len(worklist)} pairs. Estimated cost: ${est:.2f}", file=sys.stderr)

    if args.dry_run:
        print_dry_run(worklist, question_bank)
        return

    if not args.yes:
        print("Pass --yes to actually make these (paid) API calls. "
              "Exiting without doing anything.", file=sys.stderr)
        return

    asyncio.run(run(worklist, question_bank, args.concurrency, args.timeout))


if __name__ == "__main__":
    main()
