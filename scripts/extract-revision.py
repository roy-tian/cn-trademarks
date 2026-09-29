"""Extract the CN NCL13-2026 revision list into per-listing operations.

Usage: python scripts/extract-revision.py <revision.pdf> [output.tsv]
Source: 《NCL(13-2026)版中文版和区分表修改内容》 (see NOTICE.md). The PDF has a
text layer laid out as a 类 / 位置 / 修改内容 table; PyMuPDF's table finder
keeps every change next to its similar group, which the flat text does not.

Each output row is one operation on one listing (code, name, group), in
document order.  build-snapshots.py applies them to the NCL12 snapshot.
Class-title and note (注释/注) edits are abbreviated in the source and are
not extracted; they are handled in build-snapshots.py.
"""

import re
import sys
from pathlib import Path

import pymupdf

if len(sys.argv) < 2:
    raise SystemExit("usage: extract-revision.py <revision.pdf> [output.tsv]")
output = Path(sys.argv[2] if len(sys.argv) > 2 else "scripts/ncl13-2026-revision.tsv")

cells = []  # [group, content] in document order
for page in pymupdf.open(sys.argv[1]):
    for table in page.find_tables().tables:
        for row in table.extract():
            _, position, content = [(c or "").replace("\n", "") for c in row]
            if position == "位置":
                continue
            if position:
                cells.append([position, content])
            elif content and cells:
                cells[-1][1] += content  # row continued on the next page

CODE = r"C?\d{6}"
entry_re = re.compile(rf"^(.*?)({CODE})(?:【[^】]*】)?$")
rename_re = re.compile(rf"({CODE})“([^”]+)”(?:修改为|改为)“([^”]+)”")
renumber_re = re.compile(rf"“?([^“”，]+?)”?编号由({CODE})改为({CODE})")
ops = []
consumed = set()


def clean(name):
    return re.sub(r"\s+", "", name)


for group, content in cells:
    if not re.fullmatch(r"\d{4}", group):
        continue  # 标题 / 注释 rows
    for bullet in content.split("Ø"):
        text = clean(bullet)
        text = re.sub(r"^第[一二三四五六七八九十]+(?:部分|自然段)：", "", text)
        if not text or re.match(r"^(?:增加注|删除注|原注|注|第[一二三四五六七八九十]+部分注)", text):
            continue
        if text == "本类似群整体删除" or text.startswith("本类似群整体删除【"):
            ops.append((group, "group-delete", "", "", ""))
            continue
        if m := re.fullmatch(r"类似群名称修改为“(.+)”", text):
            ops.append((group, "group-rename", "", "", m[1]))
            continue
        if m := re.fullmatch(r"类似群名称：(.+)", text):
            ops.append((group, "group-new", "", "", m[1]))
            continue
        # A rename can trail an addition list in the same bullet (2501).
        renames = rename_re.findall(text)
        renumbers = renumber_re.findall(text)
        text = rename_re.sub("", renumber_re.sub("", text)).strip("，")
        if m := re.fullmatch(r"(增加|删除)：(.+)", text):
            kind = "add" if m[1] == "增加" else "delete"
            # The text layer drops line-end commas ("…450277防护用头盔出租450278" in 4505).
            entries = re.sub(rf"(?<!\d)({CODE})(?=[^\d，【])", r"\1，", m[2])
            for part in entries.split("，"):
                if not part or re.fullmatch(r"【[^】]*】", part):
                    continue  # e.g. "电暖脚套110088，【修改后移入2509】"
                em = entry_re.match(part)
                if not em or not em[1]:
                    raise SystemExit(f"{group}: unparsed {kind} entry {part!r}")
                ops.append((group, kind, em[2], em[1], ""))
                consumed.add(em[2])
        elif text:
            raise SystemExit(f"{group}: unparsed bullet {text!r}")
        for code, old, new in renames:
            ops.append((group, "rename", code, old, new))
            consumed.add(code)
        for name, old, new in renumbers:
            ops.append((group, "renumber", old, name, new))
            consumed.update((old, new))

# Source typo: 1620 adds 制手工艺品用绳绒织物棒 as 160142, which is 墨水* in
# 1612 and is not deleted by this revision.  WIPO NCL(13-2026) numbers the new
# term "craft chenille stems" 160412.
CODE_FIXES = {("1620", "add", "160142"): "160412"}
ops = [(g, op, CODE_FIXES.get((g, op, code), code), name, new) for g, op, code, name, new in ops]

# Every item code printed in a group row must have become an operation.
for group, content in cells:
    if re.fullmatch(r"\d{4}", group):
        body = re.sub(r"(?:增加注|删除注|注\d*(?:改为|修改为))“[^”]*”", "", clean(content))
        missing = set(re.findall(rf"(?<!\d){CODE}(?!\d)", body)) - consumed
        if missing:
            raise SystemExit(f"{group}: codes without an operation {sorted(missing)}")

with output.open("w", encoding="utf-8") as f:
    f.write("group\top\tcode\tname\tnew\n")
    for op in ops:
        f.write("\t".join(op) + "\n")
print(f"wrote {len(ops)} operations from {len(cells)} table cells to {output}")
