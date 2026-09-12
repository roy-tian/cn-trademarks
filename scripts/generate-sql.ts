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

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, chunks.join(";\n") + ";\n");
console.log(
  `wrote ${rows.length} rows in ${chunks.length - 1} statements -> ${outPath}`,
);
