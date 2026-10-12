# Dataset

Four JSON datasets, all keyed on `(paper, question_number)`. Paper stems look like
`CS1_2025`, `EE_2026`. Papers are `CS1`, `CS2`, `DA`, `EC`, `EE`, `MA`.

## Scale

| | |
|---|---|
| Rows in `responses/` and `results/` | **5,530** |
| ↳ scored | **5,460** (7 models × 12 papers × 65 questions) |
| ↳ EE 2025 buffer questions #66–75, excluded from analysis | **70** (10 × 7 models) |
| Image-based questions | 152 in the bank; 150 scored (2 fall in the buffer range) |
| Voided "Marks To All" questions | 2 (EC 2025 #8, EE 2026 #58) → 14 rows |
| Scored rows with no parseable answer | 11 (Gemini 4, Kimi 7) |

---

## `questions/<year>/<PAPER>_<year>.json`

The extracted question bank — 65 records per paper (75 for EE 2025).

| Field | Type | Notes |
|---|---|---|
| `question_number` | int | 1-based, as printed on the paper |
| `question` | string | Question text as extracted from the PDF |
| `image_url` | string \| null | Base64-encoded PNG (no `data:` prefix) for image-based questions, else null |

The same images are also stored as viewable files at
`questions/<year>/images/<PAPER>_<year>/q<N>.png`.

> Image attachment was **manually reviewed**. The automatic detector proposes 167 images;
> 152 survived review. The committed bank is the reviewed artifact — see the caveat in the
> top-level README.

## `answer_keys/<year>/<PAPER>_<year>.json`

The official GATE answer key, parsed.

| Field | Type | Notes |
|---|---|---|
| `question_number` | int | |
| `session` | int | GATE session number |
| `type` | string | `MCQ`, `MSQ` or `NAT` |
| `section` | string | `GA` (General Aptitude) or the subject code |
| `answer` | list \| string | MCQ: one letter. MSQ: several letters. NAT: a list of `[low, high]` tolerance ranges — occasionally two. Voided questions are the literal string `"MTA*"` |
| `marks` | int | 1 or 2 |

## `responses/<model>/<year>/<PAPER>_<year>.json`

**What each model actually said.** One record per question.

| Field | Type | Notes |
|---|---|---|
| `question_number` | int | Joins to every other dataset |
| `question` | string | Copy of the question text, for readability |
| `has_image` | bool | Whether the question carried an image |
| `reasoning` | string \| null | The model's reasoning trace. Null when the provider returns none (1,818 rows) |
| `completion` | string \| null | The model's visible answer text |
| `final_answer` | string \| null | Parsed from the `FINAL_ANSWER:` line. Null for the 11 rows where no parseable line was produced |
| `generation_time_s` | float \| null | **As reported by the API provider**, not client wall-clock |
| `generation_cost` | float \| null | USD, **as reported by the API provider** |

Time and cost are null for the EE 2025 buffer questions, which were never queried.

Model directory names are the full model identifiers, e.g.
`gemini-3.1-pro-preview-20260219`.

## `results/<model>/<year>/<PAPER>_<year>.json`

**How each answer was marked.** Derived — rebuilt by `make score`, never edited by hand.

| Field | Type | Notes |
|---|---|---|
| `question_number` | int | |
| `question_type` | string \| null | `MCQ`/`MSQ`/`NAT`. **Null marks a buffer question** with no official key; all analysis skips these |
| `section` | string \| null | `GA` or the subject code |
| `marks` | int \| null | Marks available |
| `has_image` | bool | |
| `correct_answer` | list \| string \| null | From the answer key; `"MTA*"` for voided questions |
| `final_answer` | string \| null | Copied from `responses/` |
| `is_correct` | bool \| null | **Null means unscorable**, not wrong — unattempted, unparseable, or a voided question |
| `marks_obtained` | number \| null | Includes MCQ negative marking of −marks/3 |
| `generation_time_s` | float \| null | |
| `generation_cost` | float \| null | |

### Reading `is_correct` correctly

`null` is not a synonym for "wrong". It means the answer could not be scored, which covers
three distinct situations: the model produced no parseable answer, the answer was not a
valid option for that question type, or the question was voided. Treating null as wrong
would understate every model's accuracy.

## `air1_scores.json`

The official GATE 2026 All India Rank 1 scores (out of 100) used as the human baseline in
Figures 1 and 2. External reference data, not produced by this pipeline.
