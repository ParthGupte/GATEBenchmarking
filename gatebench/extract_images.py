"""
Deterministic figure cropper for GATE question papers.

Reuses the question-boundary regexes from extract_questions.py, but applied
geometrically (per line bounding box, via PyMuPDF's "dict" text extraction)
instead of on the concatenated text string, so each question's start can be
located as a (page, y) position rather than a character offset.

For each question, the candidate figure region is the union bounding box of:
  - embedded raster images on the question's page span, excluding size
    classes that recur across many pages of the document (background
    watermarks and header logos share pixel dimensions on every page,
    even though PDF generators sometimes give each page's watermark a
    distinct xref -- so images are matched by (width, height) in pixels,
    not by xref).
  - vector line-art ("drawings") on the question's page span, excluding
    hairlines (near-zero width or height) -- GATE papers lay out ALL text,
    including plain non-figure MCQs, inside an invisible table grid drawn
    with 1pt-wide full-column-height vector lines, which would otherwise
    swamp every question with a false-positive "figure".

This is a first pass: it will miss figures built entirely from thin line
segments (a pure wireframe circuit with no filled/curved element), and it
may occasionally include a genuine thick table border. Both are expected to
be caught and corrected in a follow-up visual review pass, not solved here.

Output: for each data/papers/<year>/<CODE>_<year>.pdf, updates the matching
data/questions/<year>/<CODE>_<year>.json in place, filling image_url
with a base64-encoded PNG for questions where a candidate region was found
(else leaving it None). Crops are also saved as PNG files under
data/questions/<year>/images/<CODE>_<year>/q<question_number>.png for
visual review.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from gatebench.extract_questions import (
    EXTRA_BUFFER_HEADING_RE,
    QUESTION_MARKER_RE,
    SECTION_HEADER_RE,
    PAPERS_DIR,
    OUTPUT_DIR,
)

MIN_BOX_DIM = 3.0  # pt; drawings thinner than this on either axis are hairlines/table grid, not figure ink
BOILERPLATE_MIN_PAGE_COUNT = 3  # an image size-class or exact drawing rect recurring this often is page furniture
MIN_FIGURE_AREA = 900.0  # pt^2 (~30x30pt); union boxes smaller than this are treated as noise, not a figure
CROP_PADDING = 4.0  # pt
RENDER_ZOOM = 3.0  # ~216 dpi

# GATE papers lay options out in a two-column table: a narrow left column with
# just "(A)"/"(B)"/... and a wide right column with the option's content. When
# the option *content* is itself a figure (e.g. "which plot is correct?"), the
# label text sits to the left of -- outside -- the figure's own bounding box
# and would otherwise be cropped away. Detect bare option-label lines and pull
# them into the crop whenever they vertically align with the figure.
OPTION_LABEL_RE = re.compile(r"^\(?[A-D]\)?\.?$")


def find_question_markers(doc: fitz.Document) -> list[tuple[int, fitz.Rect, int, str | None]]:
    """Returns ordered list of (page_index, line_bbox, question_number, letter)
    for each real question start, skipping "Q.a - Q.b carry ..." range headers."""
    markers = []
    for pno, page in enumerate(doc):
        text_dict = page.get_text("dict", sort=True)
        for block in text_dict["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"])
                stripped = text.strip()
                if not stripped:
                    continue
                if SECTION_HEADER_RE.search(text) or EXTRA_BUFFER_HEADING_RE.search(text):
                    continue
                m = QUESTION_MARKER_RE.match(stripped)
                if m:
                    markers.append((pno, fitz.Rect(line["bbox"]), int(m.group(1)), m.group(2)))
    return markers


def boilerplate_image_sizes(doc: fitz.Document) -> set[tuple[int, int]]:
    size_page_count = Counter()
    for page in doc:
        seen = set()
        for img in page.get_images(full=True):
            size = (img[2], img[3])
            if size not in seen:
                size_page_count[size] += 1
                seen.add(size)
    return {size for size, count in size_page_count.items() if count >= BOILERPLATE_MIN_PAGE_COUNT}


def boilerplate_drawing_rects(doc: fitz.Document) -> set[tuple[int, int, int, int]]:
    rect_page_count = Counter()
    for page in doc:
        seen = set()
        for d in page.get_drawings():
            r = d["rect"]
            key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
            if key not in seen:
                rect_page_count[key] += 1
                seen.add(key)
    return {key for key, count in rect_page_count.items() if count >= BOILERPLATE_MIN_PAGE_COUNT}


def page_content_rects(page: fitz.Page, boilerplate_sizes, boilerplate_rects) -> list[fitz.Rect]:
    """Non-boilerplate raster images and non-hairline vector drawings on this page."""
    rects = []
    for img in page.get_images(full=True):
        size = (img[2], img[3])
        if size in boilerplate_sizes:
            continue
        for r in page.get_image_rects(img[0]):
            rects.append(r)
    for d in page.get_drawings():
        r = d["rect"]
        if r.width < MIN_BOX_DIM or r.height < MIN_BOX_DIM:
            continue
        key = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
        if key in boilerplate_rects:
            continue
        rects.append(r)
    return rects


def question_slices(markers, n_pages: int):
    """Yields (question_number, letter, [(page_index, y0, y1), ...]) for each
    question, covering from its marker to just before the next marker (or
    end of its own page, for the very last question)."""
    for i, (pno, bbox, qnum, letter) in enumerate(markers):
        y_start = bbox.y0
        if i + 1 < len(markers):
            end_pno, end_bbox, _, _ = markers[i + 1]
        else:
            end_pno, end_bbox = pno, None

        slices = []
        if end_bbox is None:
            slices.append((pno, y_start, None))
        elif end_pno == pno:
            slices.append((pno, y_start, end_bbox.y0))
        else:
            slices.append((pno, y_start, None))
            for mid in range(pno + 1, end_pno):
                slices.append((mid, None, None))
            slices.append((end_pno, None, end_bbox.y0))
        yield qnum, letter, slices


def option_label_rects(page: fitz.Page, band_top: float, band_bottom: float, left_of_x: float) -> list[fitz.Rect]:
    """Bare "(A)"/"(B)"/... label lines on `page`, vertically overlapping
    [band_top, band_bottom], sitting left of `left_of_x` -- i.e. the option
    labels for figures that are themselves the option content."""
    found = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not OPTION_LABEL_RE.match(text):
                continue
            bbox = fitz.Rect(line["bbox"])
            if bbox.y1 <= band_top or bbox.y0 >= band_bottom:
                continue
            if bbox.x1 >= left_of_x:
                continue
            found.append(bbox)
    return found


def dont_truncate_text(page: fitz.Page, rect: fitz.Rect) -> fitz.Rect:
    """get_pixmap(clip=...) rasters everything physically inside the clip
    rect, including text that never contributed to the figure bbox -- e.g. a
    diagram whose text labels (not part of any drawing/image) poke out
    slightly past the drawn shapes. Widen x only, never y: consecutive text
    lines routinely have near-zero or even negative gaps between their
    bounding boxes (ordinary paragraph leading, not just wrapped option
    text), so a y-growing version of this cannot tell "finish this option's
    wrapped line" from "swallow the whole paragraph above the figure" --
    they look geometrically identical. x-only growth can't cascade like
    that: it only ever pulls in lines already within the figure's own fixed
    y-range, which the drawings/images already established."""
    x0, x1 = rect.x0, rect.x1
    lines = [
        fitz.Rect(line["bbox"])
        for block in page.get_text("dict", sort=True)["blocks"]
        if block.get("type") == 0
        for line in block["lines"]
    ]
    for _ in range(5):
        grew = False
        for bbox in lines:
            if bbox.y1 <= rect.y0 or bbox.y0 >= rect.y1:
                continue
            if bbox.x1 <= x0 or bbox.x0 >= x1:
                continue
            if bbox.x0 < x0:
                x0, grew = bbox.x0, True
            if bbox.x1 > x1:
                x1, grew = bbox.x1, True
        if not grew:
            break
    return fitz.Rect(x0, rect.y0, x1, rect.y1)


def crop_for_question(doc: fitz.Document, slices, boilerplate_sizes, boilerplate_rects) -> bytes | None:
    best_rect = None
    best_pno = None
    best_area = 0.0

    for pno, y0, y1 in slices:
        page = doc[pno]
        page_rect = page.rect
        band_top = y0 if y0 is not None else 0.0
        band_bottom = y1 if y1 is not None else page_rect.height

        candidates = page_content_rects(page, boilerplate_sizes, boilerplate_rects)
        union = None
        for r in candidates:
            if r.y1 <= band_top or r.y0 >= band_bottom:
                continue
            union = r if union is None else union | r

        if union is None:
            continue
        area = union.width * union.height
        if area >= MIN_FIGURE_AREA and area > best_area:
            best_rect = union
            best_pno = pno
            best_area = area

    if best_rect is None:
        return None

    best_page = doc[best_pno]
    # Search for option labels only within the figure's own tight y-range
    # (not the whole question slice) -- otherwise a diagram in the question
    # stem would also vacuum up unrelated plain-text options lower on the
    # page. This only fires for rows where the option content is itself
    # figure/drawing content (so it already contributed to best_rect).
    for label_rect in option_label_rects(best_page, best_rect.y0, best_rect.y1, best_rect.x0):
        best_rect |= label_rect
    best_rect = dont_truncate_text(best_page, best_rect)

    padded = fitz.Rect(
        best_rect.x0 - CROP_PADDING,
        best_rect.y0 - CROP_PADDING,
        best_rect.x1 + CROP_PADDING,
        best_rect.y1 + CROP_PADDING,
    ) & best_page.rect

    pix = best_page.get_pixmap(clip=padded, matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
    return pix.tobytes("png")


def process_pdf(pdf_path: Path, images_dir: Path) -> dict[int, bytes]:
    doc = fitz.open(pdf_path)
    markers = find_question_markers(doc)
    boilerplate_sizes = boilerplate_image_sizes(doc)
    boilerplate_rects = boilerplate_drawing_rects(doc)

    crops: dict[int, bytes] = {}
    next_extra_num = max((qnum for _, _, qnum, letter in markers if letter is None), default=0) + 1
    for qnum, letter, slices in question_slices(markers, len(doc)):
        png_bytes = crop_for_question(doc, slices, boilerplate_sizes, boilerplate_rects)
        if png_bytes is None:
            continue
        out_num = qnum if letter is None else next_extra_num
        if letter is not None:
            next_extra_num += 1
        crops[out_num] = png_bytes

    doc.close()
    return crops


def main():
    pdf_paths = sorted(PAPERS_DIR.glob("*/*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {PAPERS_DIR}", file=sys.stderr)
        sys.exit(1)

    for pdf_path in pdf_paths:
        rel_dir = pdf_path.relative_to(PAPERS_DIR).parent
        json_path = OUTPUT_DIR / rel_dir / pdf_path.with_suffix(".json").name
        if not json_path.exists():
            print(f"Skipping {pdf_path}: {json_path} not found (run extract_questions.py first)", file=sys.stderr)
            continue

        images_dir = OUTPUT_DIR / rel_dir / "images" / pdf_path.stem
        images_dir.mkdir(parents=True, exist_ok=True)

        crops = process_pdf(pdf_path, images_dir)

        with open(json_path) as f:
            questions = json.load(f)

        n_with_image = 0
        for q in questions:
            png_bytes = crops.get(q["question_number"])
            if png_bytes is None:
                continue
            (images_dir / f"q{q['question_number']}.png").write_bytes(png_bytes)
            q["image_url"] = base64.b64encode(png_bytes).decode("ascii")
            n_with_image += 1

        with open(json_path, "w") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        print(f"{pdf_path.relative_to(PAPERS_DIR)}: {n_with_image}/{len(questions)} questions got a candidate image")


if __name__ == "__main__":
    main()
