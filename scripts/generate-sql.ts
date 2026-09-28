/**
 * data/nice.jsonl -> sql/postgresql/trademark_nice.sql
 * 批量 INSERT（每 500 行一条语句），转义单引号。用法: node scripts/generate-sql.ts
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

const dataPath = process.argv[2] ?? join(import.meta.dirname, "../data/nice.jsonl");
const outPath =
  process.argv[3] ?? join(import.meta.dirname, "../sql/postgresql/trademark_nice.sql");

interface NiceRow {
  code: string;
  parentCode: string | null;
  type: string;
  name: string;
  version: string;
}

const rows: NiceRow[] = readFileSync(dataPath, "utf-8")
  .split("\n")
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line) as NiceRow);

const q = (value: string | null) =>
  value == null ? "NULL" : `'${value.replaceAll("'", "''")}'`;

const BATCH = 500;
const chunks: string[] = [
  "-- 由 scripts/generate-sql.ts 生成；数据来源与提取方式见 NOTICE.md。",
];
for (let i = 0; i < rows.length; i += BATCH) {
  const values = rows
    .slice(i, i + BATCH)
    .map(
      (r) =>
        `(${q(r.code)}, ${q(r.parentCode)}, ${q(r.type)}, ${q(r.name)}, ${q(r.version)})`,
    )
    .join(",\n");
  chunks.push(
    `INSERT INTO "trademark_nice" ("code", "parent_code", "type", "name", "version") VALUES\n${values}`,
  );
}

// 同码同义词以全角逗号合并进 name，单一别名精确匹配查不到；
// 此视图把 item 的合并名称拆为别名行（类别/群组标题含合法逗号，不拆）。
// 只保留括号平衡的完整别名：括号内含全角逗号的名称（如 C070359、C200016）
// 产生的残缺片段不出现在视图中，其原名称仍可在主表全文检索。
chunks.push(
  `CREATE OR REPLACE VIEW "trademark_nice_alias" AS
SELECT "code", "parent_code", "type", trim("alias") AS "alias"
FROM "trademark_nice", unnest(string_to_array("name", '，')) AS "alias"
WHERE "type" = 'item'
  AND length(translate("alias", '（(', '')) = length(translate("alias", '）)', ''))`,
);

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, chunks.join(";\n") + ";\n");
console.log(
  `wrote ${rows.length} rows in ${chunks.length - 1} statements -> ${outPath}`,
);
