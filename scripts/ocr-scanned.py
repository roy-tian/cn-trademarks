"""OCR one scanned Chinese classification PDF into positioned JSONL lines.

Usage: python scripts/ocr-scanned.py <year> <pdf> <output.jsonl> [first-page] [scale]
       python scripts/ocr-scanned.py --gaps <year> <pdf> <output.jsonl> <ocr.jsonl>...
Requires PyMuPDF, NumPy and rapidocr-onnxruntime. Pages are one-indexed.

RapidOCR's detector skips a different few lines at each render scale.  Run it
at 1.3 (the default) and 1.6, then run --gaps over both runs: it re-reads at
2.5x every strip tall enough to hide a line.  extract-scanned.py merges all
three runs.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

gaps_mode = sys.argv[1:2] == ["--gaps"]
args = sys.argv[2:] if gaps_mode else sys.argv[1:]
if len(args) < (4 if gaps_mode else 3):
    raise SystemExit(
        "usage: ocr-scanned.py <year> <pdf> <output.jsonl> [first-page] [scale]\n"
        "       ocr-scanned.py --gaps <year> <pdf> <output.jsonl> <ocr.jsonl>..."
    )

year, pdf_path, output_path = args[:3]
output = Path(output_path)


def read_runs(path):
    """Complete records of an OCR run, dropping a torn line left by a kill."""
    records = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record["source"] == year:
            records.append(record)
    return records


done = set()
if output.exists():
    raw = output.read_bytes()
    complete, newline, torn = raw.rpartition(b"\n")
    if torn:  # truncate the torn partial line left by a killed previous run
        keep = complete + newline if complete else b""
        with output.open("r+b") as fix:
            fix.truncate(len(keep))
    done = {record["page"] for record in read_runs(output)}

document = pymupdf.open(pdf_path)
ocr = RapidOCR()


def read(page_number, scale, top=0.0, bottom=None):
    """OCR a horizontal strip (the whole page by default) of one page."""
    page = document[page_number - 1]
    clip = pymupdf.Rect(0, top, page.rect.width, bottom or page.rect.height)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
    image = np.frombuffer(pixmap.samples, np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    detected, _ = ocr(image)
    return [
        {
            "x": round(min(point[0] for point in box) / scale, 1),
            "y": round(top + min(point[1] for point in box) / scale, 1),
            "text": text,
            "score": round(float(confidence), 3),
        }
        for box, text, confidence in detected or []
    ]


# Body text runs from y≈90 (2022) or y≈100 (2025) to y≈750 in 19–20 pt steps
# and paragraphs add about 10 pt; a gap over 34 pt can hide a skipped line
# (headings too, which only costs a read).  The running header sits above 70.
TOP, BOTTOM = 70, 770


def missing_strips(lines):
    rows = sorted(z["y"] for z in lines if TOP < z["y"] < BOTTOM)
    bounds = [TOP] + [y for i, y in enumerate(rows) if i == 0 or y - rows[i - 1] > 6] + [BOTTOM]
    for above, below in zip(bounds, bounds[1:]):
        if below - above > 34:
            yield above + 12, below


runs = {}
scale = float(args[4]) if not gaps_mode and len(args) > 4 else 1.3
if gaps_mode:
    for path in args[3:]:
        for record in read_runs(path):
            runs.setdefault(record["page"], []).extend(record["lines"])
    pages = sorted(runs)
else:
    first_page = int(args[3]) if len(args) > 3 else 1
    pages = range(first_page, len(document) + 1)

output.parent.mkdir(parents=True, exist_ok=True)
with output.open("a", encoding="utf-8") as stream:
    for page_number in pages:
        if page_number in done:
            continue
        if gaps_mode:
            lines = [
                z
                for top, bottom in missing_strips(runs[page_number])
                for z in read(page_number, 2.5, top, bottom)
            ]
        else:
            lines = read(page_number, scale)
        lines.sort(key=lambda line: (line["y"], line["x"]))
        record = {"source": year, "page": page_number, "lines": lines}
        if gaps_mode:
            record["gaps"] = True
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        if page_number % 25 == 0:
            print(f"{year}: OCR through PDF page {page_number}/{len(document)}", flush=True)
