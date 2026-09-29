"""Parse positioned OCR lines into a draft Chinese classification snapshot.

Usage: python scripts/extract-scanned.py <2022|2025> <ocr.jsonl>... <draft.jsonl>
Pass every OCR run of the PDF (ocr-scanned.py at scales 1.3 and 1.6, then
--gaps): the first run is the base and later runs fill in lines it skipped or
offer another reading of the same line.
The draft is raw OCR: build-snapshots.py cross-checks every name against the
other CN sources and applies the reviewed corrections.
"""

import bisect
import collections
import difflib
import json
import re
import sys
from pathlib import Path

if len(sys.argv) < 4:
    raise SystemExit("usage: extract-scanned.py <2022|2025> <ocr.jsonl>... <draft.jsonl>")
source, *ocr_paths, out = sys.argv[1:]
if source not in ("2022", "2025"):
    raise SystemExit("year must be 2022 or 2025")
code_re = re.compile(r"(?<!\d)C?\d{6}(?!\d)")
by_page = {}
for ocr_path in ocr_paths:
    with Path(ocr_path).open(encoding="utf-8") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn tail left by a killed ocr-scanned.py run
            if record["source"] != source:
                continue
            if record.get("gaps"):
                # Gap reads only recover missed item lines; a strip can also
                # clip a heading into noise ("第二类" read as "第二天").
                record["lines"] = [z for z in record["lines"] if code_re.search(z["text"])]
            base = by_page.setdefault(record["page"], record)
            if base is record:
                continue
            # Add a line where the base run has nothing at that height; where
            # it has, keep this reading as an alternative for the same line.
            added = []
            for z in record["lines"]:
                same = [b for b in base["lines"] if abs(b["y"] - z["y"]) <= 6]
                if not same:
                    added.append(z)
                elif len(same) == 1:
                    same[0].setdefault("alts", []).append(z["text"])
            base["lines"] = sorted(base["lines"] + added, key=lambda z: (z["y"], z["x"]))
pages = sorted(by_page.values(), key=lambda p: p["page"])
for p in pages:
    for z in p["lines"]:
        # A reading with more item codes lost less of the line.
        best = max([z["text"], *z.get("alts", [])], key=lambda t: len(code_re.findall(t)))
        if len(code_re.findall(best)) > len(code_re.findall(z["text"])):
            z["alts"] = [z["text"], *[t for t in z["alts"] if t != best]]
            z["text"] = best
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
selected = {}
for p in pages:
    for i, z in enumerate(p["lines"]):
        if z["y"] < 70 or z["y"] > 760:
            continue
        for text in [z["text"], *z.get("alts", [])]:  # a heading may read better in another run
            m = group_re.match(text)
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
    s = "".join(text for text, _ in buffer)
    # Offset where each buffered line starts, to report the page a code is on.
    starts = [0]
    for text, _ in buffer[:-1]:
        starts.append(starts[-1] + len(text))
    prev = 0
    for m in code_re.finditer(s):
        page = buffer[bisect.bisect_right(starts, m.start()) - 1][1]
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
                "page": page,
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
        # Like group headings, a class heading may read better in another run.
        cm = next(
            (m for t in [text, *z.get("alts", [])] if (m := class_re.fullmatch(t.strip()))),
            None,
        )
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
                {
                    "code": current_class,
                    "name": "",
                    "type": "class",
                    "parentCode": None,
                    "page": p["page"],
                }
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
                    "page": p["page"],
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
            buffer.append((text, p["page"]))
flush()
# One row per code; ``listings`` keeps every (group, name, page) printing in
# book order, which build-snapshots.py needs to apply per-group revisions.
bycode = {}
dupes = []
for row in items:
    listing = [row["parentCode"], row["name"], row["page"]]
    old = bycode.get(row["code"])
    if old:
        if old["parentCode"] != row["parentCode"]:
            dupes.append((row["code"], old["parentCode"], row["parentCode"]))
        if row["name"] and row["name"] not in old["name"].split("，"):
            old["name"] += "，" + row["name"]
        old["listings"].append(listing)
    else:
        bycode[row["code"]] = row
        row["listings"] = [listing]
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
