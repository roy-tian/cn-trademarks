"""Extract NCL(10-2016) from the official text-layer PDF.

Usage: python scripts/extract-2016.py <official.pdf> [output.jsonl]
Source: https://web.archive.org/web/20161111093519id_/http://sbj.saic.gov.cn/sbsq/spfl/200902/W020161009303205832663.pdf
Requires PyMuPDF. A few source text-layer defects are corrected below.
"""

import json
import re
import sys
from pathlib import Path

import fitz

if len(sys.argv) < 2:
    raise SystemExit("usage: extract-2016.py <official.pdf> [output.jsonl]")
pdf = fitz.open(sys.argv[1])
output = (
    Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/snapshots/ncl10-2016.jsonl")
)
class_pattern = re.compile(r"^\s*第[一二三四五六七八九十]+类\s*$")
group_pattern = re.compile(r"^\s*(\d{4})\s+([^\d].*)$")
part_pattern = re.compile(r"^\s*(?:[（(][一二三四五六七八九十]+[）)]|※)")
code_pattern = re.compile(r"(?<!\d)(C?\d{6})(?!\d)")
classes = []
groups = []
items = []
duplicate = []
leftovers = []
current_class = None
current_group = None
class_title = []
title_mode = False
item_mode = False
item_buffer = []


def flush_items():
    global item_buffer
    if not current_group or not item_buffer:
        return
    s = "".join(item_buffer)
    prev = 0
    for m in code_pattern.finditer(s):
        raw = s[prev : m.start()]
        # Only remove separators and an explicit section marker such as
        # ``（一）``.  A Chinese numeral can be part of the item name
        # (例如 ``一氧化二氮``), and a leading parenthesis can be meaningful.
        name = re.sub(r"^[,，\s※*]+", "", raw).strip()
        name = re.sub(r"^[（(][一二三四五六七八九十]+[）)]", "", name)
        name = re.sub(r"^[,，\s※*]+", "", name).strip()
        name = re.sub(r"\s+", "", name)
        if name:
            items.append(
                {
                    "code": m.group(),
                    "name": name,
                    "type": "item",
                    "parentCode": current_group,
                }
            )
        else:
            leftovers.append((current_group, m.group(), repr(raw)))
        prev = m.end()
    if s[prev:].strip(",，※* \n"):
        leftovers.append((current_group, "tail", s[prev:][:60]))
    item_buffer = []


for pi, page in enumerate(pdf):
    for line in page.get_text(sort=True).splitlines():
        if re.match(r"^\s*\d{1,3}\s*$", line):
            continue
        if class_pattern.match(line):
            flush_items()
            current_group = None
            item_mode = False
            current_class = f"{len(classes) + 1:02d}"
            class_title = []
            title_mode = True
            classes.append(
                {"code": current_class, "name": "", "type": "class", "parentCode": None}
            )
            continue
        gm = group_pattern.match(line)
        g = (gm.group(1), gm.group(2).strip()) if gm else None
        if not g and current_class == "09" and "0918 工业用X" in line:
            g = ("0918", "工业用X光机械设备")
        elif not g and current_class == "10" and "1003 医疗用电子" in line:
            g = ("1003", "医疗用电子、核子、电疗和X光设备")
        if title_mode:
            if "【注释】" in line or g:
                classes[-1]["name"] = re.sub(r"\s+", "", "".join(class_title))
                title_mode = False
            else:
                class_title.append(line)
            if not g:
                continue
        if g and current_class and g[0][:2] == current_class:
            flush_items()
            current_group = g[0]
            item_mode = True
            groups.append(
                {
                    "code": current_group,
                    "name": g[1],
                    "type": "group",
                    "parentCode": current_class,
                }
            )
            continue
        if not current_group:
            continue
        if (
            current_group == "1001"
            and line.strip() == "电疗、医疗用X光设备、器械及仪器"
        ):
            groups[-1]["name"] += line.strip()
            continue
        if re.match(r"^\s*注[:：]", line):
            flush_items()
            item_mode = False
            continue
        if part_pattern.match(line) and code_pattern.search(line):
            item_mode = True
        if item_mode:
            item_buffer.append(line)
flush_items()
bycode = {}
for r in items:
    old = bycode.get(r["code"])
    if old:
        if old["parentCode"] != r["parentCode"]:
            duplicate.append((r["code"], old["parentCode"], r["parentCode"]))
        if r["name"] not in old["name"].split("，"):
            old["name"] += "，" + r["name"]
    else:
        bycode[r["code"]] = r
# The PDF prints C40006 (five digits); later editions confirm C400006.
bycode["C400006"] = {
    "code": "C400006",
    "name": "碾磨加工",
    "type": "item",
    "parentCode": "4001",
}
# The PDF text layer interleaves CD/DVD and 播放机.
bycode["090632"]["name"] = "CD播放机"
bycode["090685"]["name"] = "DVD播放机"
# A section separator is attached to this C item in the PDF text layer.
bycode["C070437"]["name"] = "水力发电设备"
assert len(classes) == 45 and len(groups) == 497 and len(bycode) == 10253
assert leftovers == [("4001", "tail", "   ※碾磨加工C40006")], leftovers
rows = classes + groups + list(bycode.values())
for row in rows:
    row["version"] = "2016"
rows.sort(key=lambda r: r["code"])
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
print(
    f"wrote {len(rows)} rows to {output}; {len(duplicate)} cross-group listings collapsed"
)
