"""OCR one scanned Chinese classification PDF into positioned JSONL lines.

Usage: python scripts/ocr-scanned.py <year> <pdf> <output.jsonl> [first-page]
Requires PyMuPDF, NumPy and rapidocr-onnxruntime. Pages are one-indexed.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

if len(sys.argv) < 4:
    raise SystemExit("usage: ocr-scanned.py <year> <pdf> <output.jsonl> [first-page]")

year, pdf_path, output_path = sys.argv[1:4]
first_page = int(sys.argv[4]) if len(sys.argv) > 4 else 1
output = Path(output_path)
done = set()
if output.exists():
    raw = output.read_bytes()
    complete, newline, torn = raw.rpartition(b"\n")
    if torn:  # truncate the torn partial line left by a killed previous run
        keep = complete + newline if complete else b""
        with output.open("r+b") as fix:
            fix.truncate(len(keep))
        raw = keep
    for line in raw.decode("utf-8", errors="ignore").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # unparsable line left by a killed previous run
        if record["source"] == year:
            done.add(record["page"])

document = pymupdf.open(pdf_path)
ocr = RapidOCR()
scale = 1.3
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("a", encoding="utf-8") as stream:
    for page_number in range(first_page, len(document) + 1):
        if page_number in done:
            continue
        pixmap = document[page_number - 1].get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), alpha=False
        )
        image = np.frombuffer(pixmap.samples, np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        detected, _ = ocr(image)
        lines = []
        for box, text, confidence in detected or []:
            lines.append(
                {
                    "x": round(min(point[0] for point in box) / scale, 1),
                    "y": round(min(point[1] for point in box) / scale, 1),
                    "text": text,
                    "score": round(float(confidence), 3),
                }
            )
        lines.sort(key=lambda line: (line["y"], line["x"]))
        stream.write(
            json.dumps(
                {"source": year, "page": page_number, "lines": lines},
                ensure_ascii=False,
            )
            + "\n"
        )
        stream.flush()
        if page_number % 25 == 0:
            print(
                f"{year}: OCR through PDF page {page_number}/{len(document)}",
                flush=True,
            )
