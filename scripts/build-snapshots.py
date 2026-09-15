"""Combine the Chinese OCR drafts with accepted international terms from TIPO.

Usage: python scripts/build-snapshots.py <2022-draft.jsonl> <2025-draft.jsonl>
       <2022-bilateral.ods> <2025-bilateral.ods> <2026-bilateral.ods> <output-dir>
Run from the repository root after extract-2016.py and extract-scanned.py.
"""

import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

if len(sys.argv) != 7:
    raise SystemExit(
        "usage: build-snapshots.py <2022-draft> <2025-draft> <2022.ods> <2025.ods> <2026.ods> <output-dir>"
    )
draft_files = {2022: sys.argv[1], 2025: sys.argv[2]}
ods_files = {2022: sys.argv[3], 2025: sys.argv[4], 2026: sys.argv[5]}
output_dir = Path(sys.argv[6])


def read_ods(path):
    ns = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    sheet = next(root.iter(ns + "table"))
    result = {}
    for row in sheet.findall(ns + "table-row")[1:]:
        # Expand number-columns-repeated so collapsed empty cells keep their
        # column positions, and pad omitted trailing cells.
        cells = []
        for cell in row:
            repeat = min(int(cell.get(ns + "number-columns-repeated") or 1), 9 - len(cells))
            cells.extend(["".join(cell.itertext()).strip()] * repeat)
            if len(cells) >= 9:
                break
        cells += [""] * (9 - len(cells))
        if not re.fullmatch(r"\d{6}", cells[1]):
            continue
        if cells[6] not in ("O", "〇", "○"):
            print(f"{path}: skip {cells[1]} status {cells[6]!r}", file=sys.stderr)
            continue
        code = cells[1]
        data = result.setdefault(code, {"names": [], "groups": []})
        if cells[7] and cells[7] not in data["names"]:
            data["names"].append(cells[7])
        for group in re.findall(r"\d{4}", cells[8]):
            if group not in data["groups"]:
                data["groups"].append(group)
    for code, data in result.items():
        if not data["names"] or not data["groups"]:
            raise ValueError(f"{path}: incomplete {code}")
    return result


def rows(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def bycode(arr, kind="item"):
    return {r["code"]: r for r in arr if r["type"] == kind}


def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


def save(path, arr):
    arr.sort(key=lambda r: r["code"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in arr:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


base = rows("data/snapshots/ncl10-2016.jsonl")
current = rows("data/nice.jsonl")
base_items = bycode(base)
current_items = bycode(current)
base_groups = bycode(base, "group")
current_groups = bycode(current, "group")
source2025C = {
    c: r
    for c, r in current_items.items()
    if c.startswith("C") and r.get("version") == "2025"
}
manual_group = {
    "1001": "外科、医疗和兽医用仪器、器械、设备，不包括电子、核子、电疗、医疗用X光设备、器械及仪器",
    "0748": "发电机，非陆地车辆用马达和引擎，马达和引擎零部件",
}
verified_2022_c = [
    "C010012",
    "C010013",
    "C010014",
    "C010015",
    "C010016",
    "C010158",
    "C010159",
    "C010160",
    "C010161",
    "C010162",
    "C010163",
    "C010177",
    "C010178",
    "C010179",
    "C010180",
    "C010212",
    "C060001",
    "C060002",
    "C060003",
    "C060004",
    "C060005",
    "C060007",
    "C060043",
    "C070344",
    "C070415",
    "C070416",
    "C070417",
    "C300039",
    "C300040",
    "C300041",
    "C300042",
    "C300043",
    "C300044",
]


def clean_groups(prototype, year):
    group_rows = [copy.deepcopy(r) for r in prototype if r["type"] == "group"]
    for r in group_rows:
        c = r["code"]
        b = base_groups.get(c)
        u = current_groups.get(c)
        if c == "1001" or c == "0748":
            r["name"] = manual_group[c]
        elif (
            b
            and u
            and norm(b["name"]) == norm(u["name"])
            or c
            in [
                "1207",
                "1915",
                "0505",
                "2102",
                "2511",
                "1109",
                "0903",
                "0618",
                "1618",
                "0114",
            ]
            and u
        ):
            r["name"] = u["name"]
        r["version"] = str(year)
    return group_rows


def build(year):
    ods = read_ods(ods_files[year])
    proto = rows(draft_files[year])
    proto_items = bycode(proto)
    all_groups = clean_groups(proto, year)
    group_codes = {r["code"] for r in all_groups}
    for data in ods.values():
        for g in data["groups"]:
            if g not in group_codes:
                source = current_groups.get(g) or base_groups.get(g)
                if not source:
                    raise ValueError((year, g, "missing group title"))
                all_groups.append(
                    {
                        "code": g,
                        "name": source["name"],
                        "type": "group",
                        "parentCode": g[:2],
                        "version": str(year),
                    }
                )
                group_codes.add(g)
    result = [copy.deepcopy(r) for r in proto if r["type"] == "class"] + all_groups
    for r in result:
        r["version"] = str(year)
    for code, data in ods.items():
        groups = data["groups"]
        parent = proto_items.get(code, {}).get("parentCode")
        if parent not in groups:
            parent = groups[0]
        if parent not in group_codes:
            raise ValueError((year, code, parent, "group missing"))
        result.append(
            {
                "code": code,
                "name": "，".join(data["names"]),
                "type": "item",
                "parentCode": parent,
                "version": str(year),
            }
        )
    citems = {
        code: copy.deepcopy(r)
        for code, r in proto_items.items()
        if code.startswith("C")
    }
    if year == 2022:
        for c in verified_2022_c:
            source = source2025C.get(c) or base_items[c]
            citems[c] = {
                "code": c,
                "name": source["name"],
                "type": "item",
                "parentCode": source["parentCode"],
            }
        for c, r in citems.items():
            b = base_items.get(c)
            u = source2025C.get(c)
            ocr = r["name"]
            if c in verified_2022_c:
                continue
            if b and norm(ocr) == norm(b["name"]):
                continue
            if u and norm(ocr) == norm(u["name"]):
                continue
            if b and u and norm(b["name"]) == norm(u["name"]):
                r["name"] = u["name"]
            elif c == "C030041":
                r["name"] = "桉叶油"
    elif year == 2025:
        for c, r in source2025C.items():
            if c not in citems:
                citems[c] = copy.deepcopy(r)
        for c, r in citems.items():
            u = source2025C.get(c)
            if u:
                r["name"] = u["name"]
                r["parentCode"] = u["parentCode"]
                continue
            b = base_items.get(c)
            if b and norm(r["name"]) == norm(b["name"]):
                r["name"] = b["name"]
            if c == "C030041":
                r["name"] = "桉叶油"
    for c, r in citems.items():
        if r["parentCode"] not in group_codes:
            raise ValueError((year, c, r["parentCode"], "C group missing"))
        r["version"] = str(year)
    result.extend(citems.values())
    save(output_dir / f"ncl{11 if year == 2022 else 12}-{year}.jsonl", result)
    print(
        year,
        "classes",
        45,
        "groups",
        len(all_groups),
        "NCL",
        len(ods),
        "C",
        len(citems),
        "total",
        len(result),
    )


build(2022)
build(2025)
# NCL13: preserve the package's C rows and latest group memberships, correct
# international names against the official bilateral 2026 sheet.
ods = read_ods(ods_files[2026])
oldods = read_ods(ods_files[2025])
result = [copy.deepcopy(r) for r in current if r["type"] != "item"]
for r in result:
    if r["code"] == "0748":
        r["name"] = manual_group["0748"]
    if r["code"] == "1001":
        r["name"] = manual_group["1001"]
group_codes = {r["code"] for r in result if r["type"] == "group"}
# Rows where the TIPO 2026 sheet itself pairs names with the adjacent code
# (verified against the CN text): 280240-280252 are shifted by one row and
# 340001/340002 are swapped.  Trust the CN base for these codes instead.
ods2026_untrusted = {
    "280240", "280241", "280243", "280244", "280245", "280246", "280247",
    "280248", "280249", "280250", "280251", "280252", "340001", "340002",
}
# Items the sheet omits although the CN 2026 text keeps them.
ods2026_restore = {"280242"}
for code, data in ods.items():
    if code in ods2026_untrusted:
        continue
    old = current_items.get(code)
    parent = old["parentCode"] if old else None
    if parent not in data["groups"] and parent not in oldods.get(code, {}).get(
        "groups", []
    ):
        fallback = data["groups"][0]
        print(
            f"2026: {code} parent {parent} not in sheet groups {data['groups']};"
            f" using {fallback} — verify against the CN table",
            file=sys.stderr,
        )
        parent = fallback
    if parent not in group_codes:
        raise ValueError((2026, code, parent))
    names = "，".join(data["names"])
    version = old["version"] if old else "2026"
    if old:
        # Keep the * cross-group markers and any synonyms of the same-edition
        # CN base data; the bilateral sheet carries the text but not always
        # the markers or every synonym.  Take the sheet text (and stamp 2026)
        # only when it differs from the CN base.
        old_parts = [
            s[:-1] if s.endswith("*") else s for s in old["name"].split("，")
        ]
        starred = {s[:-1] for s in old["name"].split("，") if s.endswith("*")}
        if set(old_parts) >= set(names.split("，")):
            names = old["name"]
        else:
            names = "，".join(
                s + "*" if s in starred else s for s in names.split("，")
            )
            version = "2026"
    result.append(
        {
            "code": code,
            "name": names,
            "type": "item",
            "parentCode": parent,
            "version": version,
        }
    )
for code in sorted(ods2026_restore | (ods2026_untrusted & set(current_items))):
    result.append(copy.deepcopy(current_items[code]))
# Renumbered-away codes (e.g. 440092 -> C440006) are expected to be absent
# from the sheet; anything else dropped deserves a look.
dropped = sorted(
    c
    for c in current_items
    if not c.startswith("C") and c not in ods and c not in ods2026_restore
)
if dropped:
    print(f"2026: legacy items absent from the sheet: {dropped}", file=sys.stderr)
for code, r in current_items.items():
    if code.startswith("C"):
        result.append(copy.deepcopy(r))
save(output_dir / "ncl13-2026.jsonl", result)
print(
    2026,
    "classes",
    45,
    "groups",
    len(group_codes),
    "NCL",
    len(ods),
    "C",
    sum(r["type"] == "item" and r["code"].startswith("C") for r in result),
    "total",
    len(result),
)
