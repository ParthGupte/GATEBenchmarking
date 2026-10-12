# GATEBench

Benchmarking seven frontier large language models on the **Graduate Aptitude Test in
Engineering (GATE)** — six test papers from 2025 and 2026, 65 questions each, graded under
the official GATE marking scheme and compared against the All India Rank 1 (AIR-1) human
topper.

This repository contains everything behind the paper *"And the AIR-1 in GATE goes to..."*
(Gupte & Seelamantula, manuscript under review at IEEE Transactions on Education): the
question-extraction code, the extracted question bank and official answer keys, **every raw
model response including its reasoning trace**, the grading pipeline, and the generators for
all nine figures and both tables.

```bash
pip install -r requirements.txt
make all        # rebuilds every figure and table from the committed data
```

That one command is free, takes about a minute, and reproduces the paper's results exactly.

---

## What was measured

| | |
|---|---|
| **Models** | Claude Opus 4.7, Gemini 3.1 Pro, GPT‑5.5, Grok 4.3, Kimi K2.6, Mistral Large 3, Qwen3.6 Plus |
| **Papers** | CS1, CS2 (Computer Science), DA (Data Science & AI), EC (Electronics & Communication), EE (Electrical), MA (Mathematics) |
| **Years** | GATE 2025 and GATE 2026 |
| **Scale** | 5,460 graded model answers (7 models × 12 papers × 65 questions) |

GATE 2026 was held in February 2026 and its answer keys were released in April 2026 — after
every evaluated model's December 2025 training cut-off. The 2025 papers were almost
certainly in training data; the 2026 papers were not. That contrast is the point of
benchmarking both years.

---

## Reproducing the paper

Each figure below is written to `figures/` by `make figures`.

| Paper | File |
|---|---|
| **Fig. 1** — per-paper model scores vs AIR-1 | `combined_model_comparison_2025_vs_2026_vs_air1_3x2.png` |
| **Fig. 2** — average performance per test paper | `subject_average_across_models_2025_vs_2026.png` |
| **Fig. 3** — subject-wise image vs no-image accuracy | `paperwise_image_vs_noimage_2025_vs_2026.png` |
| **Fig. 4** — model-wise image vs no-image accuracy | `modelwise_image_vs_noimage_2025_vs_2026.png` |
| **Fig. 5** — model-wise MCQ/MSQ/NAT accuracy | `modelwise_question_type_accuracy.png` |
| **Fig. 6** — paper-wise MCQ/MSQ/NAT accuracy | `paperwise_question_type_accuracy.png` |
| **Fig. 7** — model-wise General Aptitude vs subject | `modelwise_ga_vs_subject_2025_vs_2026.png` |
| **Fig. 8** — paper-wise General Aptitude vs subject | `subjectwise_ga_vs_subject_2025_vs_2026.png` |
| **Fig. 9** — overall model average across papers | `overall_model_performance_2025_vs_2026.png` |
| **Tables I & II** — generation cost and time | `tables/cost_time_tables.tex` |

Supplementary, not in the paper: `combined_model_comparison_2025_vs_2026_cost.png`,
`..._time.png`, `modelwise_cost_2025_vs_2026.png`, `subjectwise_cost_2025_vs_2026.png`
(graphical companions to Tables I and II) and a single-model GA breakdown.

### Commands

```bash
make all        # score -> figures -> tables. The headline command.
make score      # grade data/responses/ against the answer keys -> results/
make figures    # Figures 1-9 and the cost/time figures -> figures/
make tables     # Tables I and II -> tables/cost_time_tables.tex
make reports    # per-question spreadsheet + qualitative dumps -> reports/
make verify     # dataset invariants + re-parse the PDFs to check extraction
make extract    # re-run PDF extraction into build/extracted/ (never touches data/)
make benchmark  # re-query the models through the API — COSTS REAL MONEY
make help
```

`make all` overwrites the committed figures and tables, so `git diff` after running it is
itself the reproducibility check: it should come back empty.

---

## How the pipeline fits together

```
data/papers/*.pdf  ──┐
                     ├─ extract_questions + extract_images ──> data/questions/
data/keys/*.pdf   ───┴─ extract_answer_keys ────────────────> data/answer_keys/
                                                                     │
                     run_benchmark.py  (OpenRouter API) ──> data/responses/
                                                                     │
                                       score.py  ────────────────> results/
                                                                     │
                            plot_figures / plot_cost_time / build_tables
                                                                     │
                                                        figures/ + tables/
```

`data/responses/` holds what each model actually said; `results/` holds how it was marked.
They join on `question_number`. Full field-by-field schemas are in
[`data/README.md`](data/README.md).

### Marking

The official GATE scheme, implemented in `gatebench/scoring.py`:

- **MCQ** — correct scores full marks, a wrong answer scores **−marks/3** (negative marking)
- **MSQ / NAT** — correct scores full marks, wrong scores 0 (no negative marking); NAT
  answers are matched against the official tolerance range
- **Voided ("Marks To All") questions** — every model receives full marks, matching GATE's
  own policy. Two questions are affected
- **Unparseable or unattempted** — scored as null rather than wrong, so a parsing gap is
  never silently counted as a model error

Figures reporting a *score* use pooled marks-percent (negative marking included). Figures
reporting *accuracy* use correct / (correct + wrong) over attempted, scorable questions
only.

---

## Re-running the data collection

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
python -m gatebench.run_benchmark --dry-run --limit 3   # no key needed, no calls
python -m gatebench.run_benchmark --yes                 # real, paid calls
python -m gatebench.run_benchmark --consolidate         # fold results into data/responses/
python -m gatebench.score
```

Every answer in this repository was produced by querying the model through the OpenRouter
chat-completions API with the system prompt in `gatebench/prompts.py`, which asks for a
step-by-step solution ending in a machine-readable `FINAL_ANSWER:` line. Image-based
questions are sent as the question text plus the question's PNG.

**A re-run will not reproduce the committed files byte-for-byte.** Model sampling is
non-deterministic and providers update models behind a slug, so a fresh sweep produces new
generations. Treat it as an independent replication, not a rebuild. A full sweep of all
seven models costs roughly **$60** at the per-question averages in Table I.

The runner only queries questions that are missing from `data/responses/`, so it resumes
safely after an interruption.

---

## Known gaps and caveats

These are real properties of the dataset, documented rather than smoothed over:

- **11 of 5,460 answers are missing.** The model never emitted a parseable `FINAL_ANSWER:`
  line — 4 from Gemini, 7 from Kimi. They are scored as null, not as wrong.
- **1,818 rows have no reasoning trace,** because not every model and provider returns one.
  Every row has a completion.
- **EE 2025 carries 10 buffer questions (#66–75)** with no official answer key. They are
  stored for completeness but excluded from every figure, table and statistic.
- **Image attachment in the question bank is manually reviewed.** The automatic detector in
  `extract_images.py` finds 167 candidate images; 152 survived review. `make verify`
  re-parses the PDFs and confirms the question text and answer keys match exactly, and
  reports the image-count difference as expected. If you re-run extraction, use the
  committed bank rather than the raw detector output.
- **Cost and generation time are the figures reported by the API provider** for each
  generation, not client-side stopwatch measurements.

---

## Layout

```
data/
  papers/<year>/*.pdf          original GATE question papers
  keys/<year>/*.pdf            official answer keys
  questions/<year>/*.json      extracted question bank (+ images/ PNG crops)
  answer_keys/<year>/*.json    parsed answer keys
  responses/<model>/<year>/*.json   raw model output: reasoning, completion, answer
  air1_scores.json             official AIR-1 topper scores (external reference)
results/<model>/<year>/*.json  grading outcome per question (derived, rebuilt by `make score`)
figures/                       the paper's figures
tables/                        the paper's LaTeX tables
reports/                       spreadsheet and qualitative dumps (`make reports`)
gatebench/                     all code
```

---

## Citing

See [`CITATION.cff`](CITATION.cff). The paper is currently under review at *IEEE
Transactions on Education*; this README will be updated with the full reference once it is
published.

## Licence

Code is MIT (see [`LICENSE`](LICENSE)). The GATE question papers, answer keys and the
question text and images extracted from them remain the intellectual property of IISc and
the IITs, and are included here for research reproducibility only.
