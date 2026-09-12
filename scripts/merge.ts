/**
 * 合并分片提取结果（pages-*.jsonl），
 * 做结构校验后写出 data/nice.jsonl（NCL12-2025 基础层）。
 *
 * 用法: node scripts/merge.ts [extractDir] [outJsonl]
 * 校验失败（类不全、编码形态错、群组前缀不匹配）直接退出非零。
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

interface PageRecord {
  page: number;
  class?: string | null;
  classTitle?: string | null;
  groups?: { code: string; name: string }[];
  items?: { code: string; name: string }[];
  failed?: boolean;
}

const extractDir = process.argv[2] ?? join(import.meta.dirname, "../extract");
const outPath = process.argv[3] ?? join(import.meta.dirname, "../data/nice.jsonl");

const files = readdirSync(extractDir)
  .filter((f) => /^pages-.*\.jsonl$/.test(f))
  .sort();
if (files.length === 0) throw new Error(`no pages-*.jsonl under ${extractDir}`);

const records: PageRecord[] = [];
const failedPages: number[] = [];
for (const file of files) {
  for (const line of readFileSync(join(extractDir, file), "utf-8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const record = JSON.parse(trimmed) as PageRecord;
      if (record.failed) failedPages.push(record.page);
      records.push(record);
    } catch {
      console.error(`unparseable line in ${file}: ${trimmed.slice(0, 120)}`);
      process.exitCode = 1;
    }
  }
}
records.sort((a, b) => a.page - b.page);
if (failedPages.length > 0) {
  console.error(`FAILED PAGES: ${failedPages.join(",")}`);
  process.exit(1);
}

const classNames = new Map<string, string>();
const groupNames = new Map<string, string>();
const itemNames = new Map<string, string>();
const conflicts: string[] = [];

const put = (map: Map<string, string>, code: string, name: string, kind: string) => {
  const clean = name.trim();
  if (!clean) return;
  const existing = map.get(code);
  if (existing && existing !== clean) {
    conflicts.push(`${kind} ${code}: "${existing}" vs "${clean}" (page order keeps first)`);
  } else if (!existing) {
    map.set(code, clean);
  }
};

for (const record of records) {
  if (record.class && record.classTitle) {
    put(classNames, record.class.padStart(2, "0"), record.classTitle, "class");
  }
  for (const group of record.groups ?? []) {
    put(groupNames, group.code, group.name, "group");
  }
  for (const item of record.items ?? []) {
    put(itemNames, item.code, item.name, "item");
  }
}

// ---- validation ----
const errors: string[] = [];
const CODE_CLASS = /^\d{2}$/;
const CODE_GROUP = /^\d{4}$/;
const CODE_ITEM = /^(C?\d{6})$/;

for (const code of classNames.keys()) {
  if (!CODE_CLASS.test(code)) errors.push(`bad class code ${code}`);
}
const classSet = new Set(classNames.keys());
for (let n = 1; n <= 45; n++) {
  const code = String(n).padStart(2, "0");
  if (!classSet.has(code)) errors.push(`missing class ${code}`);
}

const validGroups = new Set<string>();
for (const [code, name] of groupNames) {
  if (!CODE_GROUP.test(code)) {
    errors.push(`bad group code ${code} (${name})`);
    continue;
  }
  if (!classSet.has(code.slice(0, 2))) {
    errors.push(`group ${code} prefix matches no class`);
    continue;
  }
  validGroups.add(code);
}

let cItems = 0;
for (const [code, name] of itemNames) {
  const match = CODE_ITEM.exec(code);
  if (!match) {
    errors.push(`bad item code ${code} (${name})`);
    continue;
  }
  if (code.startsWith("C")) cItems++;
  const digits = code.replace(/^C/, "");
  // 项目编号在大类内全局顺序：前 2 位是大类，前 4 位不一定是群组。
  if (!classSet.has(digits.slice(0, 2))) {
    errors.push(`item ${code} (${name}) matches no class`);
  }
}

// 群组覆盖：每个群组至少应有一个项目（仅提示）。
const groupsWithItems = new Set(
  [...itemNames.keys()].map((code) => code.replace(/^C/, "").slice(0, 4)),
);
for (const group of validGroups) {
  if (!groupsWithItems.has(group)) {
    console.warn(`WARN: group ${group} has no items`);
  }
}

console.log(
  `pages=${records.length} classes=${classNames.size} groups=${validGroups.size} items=${itemNames.size} (C-prefix ${cItems})`,
);
if (conflicts.length > 0) {
  console.warn(`name conflicts (${conflicts.length}):`);
  for (const c of conflicts.slice(0, 30)) console.warn(`  ${c}`);
}
if (errors.length > 0) {
  console.error(`validation errors (${errors.length}):`);
  for (const e of errors.slice(0, 50)) console.error(`  ${e}`);
  process.exit(1);
}

// ---- emit ----
interface NiceRow {
  code: string;
  parentCode: string | null;
  type: "class" | "group" | "item";
  name: string;
  version: string;
}
const rows: NiceRow[] = [];
for (const [code, name] of classNames) {
  rows.push({ code, parentCode: null, type: "class", name, version: "2025" });
}
for (const [code, name] of groupNames) {
  rows.push({ code, parentCode: code.slice(0, 2), type: "group", name, version: "2025" });
}
for (const [code, name] of itemNames) {
  const digits = code.replace(/^C/, "");
  // 群组归属需印刷版式，代理提取不含：以编号前 4 位作占位（仅大类前缀可靠）。
  rows.push({
    code,
    parentCode: digits.slice(0, 4),
    type: "item",
    name,
    version: "2025",
  });
}
rows.sort((a, b) => a.code.localeCompare(b.code));

mkdirSync(join(outPath, ".."), { recursive: true });
writeFileSync(outPath, rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
console.log(`wrote ${rows.length} rows -> ${outPath}`);
