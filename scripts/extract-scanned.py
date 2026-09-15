"""Parse positioned OCR lines into a draft Chinese classification snapshot.

Usage: python scripts/extract-scanned.py <2022|2025> <ocr.jsonl> <draft.jsonl>
The draft is combined with the bilateral ODS files by build-snapshots.py.
"""

import collections
import difflib
import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: extract-scanned.py <2022|2025> <ocr.jsonl> <draft.jsonl>")
source, ocr_path, out = sys.argv[1:4]
if source not in ("2022", "2025"):
    raise SystemExit("year must be 2022 or 2025")
with Path(ocr_path).open(encoding="utf-8") as stream:
    pages = []
    for line in stream:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn tail left by a killed ocr-scanned.py run
        if record["source"] == source:
            pages.append(record)
    pages.sort(key=lambda p: p["page"])
if source == "2025":
    pages = [p for p in pages if p["page"] >= 29]
known_groups = collections.defaultdict(list)
for f in ["data/snapshots/ncl10-2016.jsonl", "data/nice.jsonl"]:
    with Path(f).open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["type"] == "group":
                known_groups[row["code"]].append(row["name"])


def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


group_re = re.compile(r"^\s*#?\s*(\d{4})(?!\d)\s*(.+)$")
code_re = re.compile(r"(?<!\d)C?\d{6}(?!\d)")
selected = {}
for p in pages:
    for i, z in enumerate(p["lines"]):
        if z["y"] < 70 or z["y"] > 760:
            continue
        m = group_re.match(z["text"])
        if not m or m[1] not in known_groups or code_re.search(m[2]):
            continue
        name = m[2].strip()
        score = max(
            difflib.SequenceMatcher(None, norm(name), norm(x)).ratio()
            for x in known_groups[m[1]]
        )
        if score < 0.65:
            continue
        prev = selected.get(m[1])
        if not prev or score > prev[0]:
            selected[m[1]] = (score, p["page"], i, name)
selected_positions = {
    (page, i): (code, name, score) for code, (score, page, i, name) in selected.items()
}
classes = []
groups = []
items = []
leftovers = []
current_class = None
current_group = None
item_mode = False
title_mode = False
class_title = []
buffer = []
class_re = re.compile(r"^第([一二三四五六七八九十]+)类$")
part_re = re.compile(r"^[（(][一二三四五六七八九十]+[）)]|^※")
CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_int(numeral):
    """第X类 numeral -> int, so a missed heading fails loudly instead of
    silently shifting every later class code (they are assigned by count)."""
    total = tmp = 0
    for ch in numeral:
        if ch in CN_DIGITS:
            tmp = CN_DIGITS[ch]
        elif ch == "十":
            total += (tmp or 1) * 10
            tmp = 0
    return total + tmp


def flush():
    global buffer
    if not current_group or not buffer:
        return
    s = "".join(buffer)
    prev = 0
    for m in code_re.finditer(s):
        raw = s[prev : m.start()]
        # Keep meaningful leading numerals/parentheses; remove only list
        # separators and a complete section marker such as ``（一）``.
        name = re.sub(r"^[，,\s※*]+", "", raw)
        name = re.sub(r"^[（(][一二三四五六七八九十]+[）)]", "", name)
        name = re.sub(r"^[，,\s※*]+", "", name).strip()
        name = re.sub(r"\s+", "", name)
        items.append(
            {
                "code": m.group(),
                "name": name,
                "type": "item",
                "parentCode": current_group,
            }
        )
        prev = m.end()
    if s[prev:].strip("，,※* "):
        leftovers.append((current_group, s[prev:][:60]))
    buffer = []


for p in pages:
    first_content = True
    for i, z in enumerate(p["lines"]):
        text = z["text"].strip()
        if z["y"] < 70 or z["y"] > 760:
            continue
        if first_content:
            first_content = False
            if (
                current_group
                and not item_mode
                and z["x"] < 95
                and code_re.search(text)
                and not text.startswith("注")
            ):
                item_mode = True
        pos = (p["page"], i)
        cm = class_re.fullmatch(text)
        if cm and z["x"] > 170:
            number = cn_int(cm.group(1))
            if number != len(classes) + 1:
                raise SystemExit(
                    f"class heading 第{cm.group(1)}类 is number {number}, expected"
                    f" {len(classes) + 1} — a heading was probably misread"
                )
            flush()
            current_group = None
            item_mode = False
            current_class = f"{number:02d}"
            classes.append(
                {"code": current_class, "name": "", "type": "class", "parentCode": None}
            )
            class_title = []
            title_mode = True
            continue
        g = selected_positions.get(pos)
        if title_mode:
            if "【注释】" in text or g:
                classes[-1]["name"] = "".join(class_title)
                title_mode = False
            else:
                class_title.append(text)
            if not g:
                continue
        if g and current_class and g[0][:2] == current_class:
            flush()
            current_group = g[0]
            item_mode = True
            groups.append(
                {
                    "code": g[0],
                    "name": g[1],
                    "type": "group",
                    "parentCode": current_class,
                }
            )
            continue
        if not current_group:
            continue
        if re.match(r"^[①②]?注[:：]|^[1-9][.．、]", text):
            flush()
            item_mode = False
            continue
        if part_re.match(text) and code_re.search(text):
            item_mode = True
        if item_mode:
            buffer.append(text)
flush()
bycode = {}
dupes = []
for row in items:
    old = bycode.get(row["code"])
    if old:
        if old["parentCode"] != row["parentCode"]:
            dupes.append((row["code"], old["parentCode"], row["parentCode"]))
        if row["name"] and row["name"] not in old["name"].split("，"):
            old["name"] += "，" + row["name"]
    else:
        bycode[row["code"]] = row
# Confirmed visual corrections for characters that RapidOCR confuses in the
# Chinese supplemental list.  Applying them here keeps the intermediate draft
# correct even when it is inspected or reused without the assembly step.
OCR_FIXES = {
    "C010053": "己二酸",
    "C010111": "己醇",
    "C010112": "环己醇",
    "C070362": "（管道）疏通挖泥车",
}
for code, name in OCR_FIXES.items():
    if code in bycode:
        bycode[code]["name"] = name
rows = classes + groups + list(bycode.values())
rows.sort(key=lambda r: r["code"])
Path(out).parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
print(
    "pages",
    len(pages),
    "classes",
    len(classes),
    "groups",
    len(groups),
    "items",
    len(bycode),
    "empty",
    sum(not r["name"] for r in bycode.values()),
    "dupes",
    len(dupes),
    "leftovers",
    len(leftovers),
)
print("first leftovers", leftovers[:12])
print(
    "bad names",
    [(r["code"], r["name"][:80]) for r in bycode.values() if len(r["name"]) > 80][:12],
)
print("last groups", [(r["code"], r["name"]) for r in groups[-10:]])
