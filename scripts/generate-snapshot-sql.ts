/** Generate the four complete NCL edition snapshots for PostgreSQL. */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { readSnapshot, snapshotPath, snapshots } from "./snapshot-data.ts";

const outPath = process.argv[2] ??
  join(import.meta.dirname, "../sql/postgresql/trademark_nice_snapshots.sql");

const q = (value: string | null | undefined) =>
  value == null ? "NULL" : `'${value.replaceAll("'", "''")}'`;
const chunks: string[] = [
  "-- Complete Chinese NCL snapshots. Sources and limitations: NOTICE.md.",
  `CREATE TABLE IF NOT EXISTS "trademark_nice_snapshot" (
  "edition" integer NOT NULL,
  "edition_year" integer NOT NULL,
  "code" text NOT NULL,
  "parent_code" text,
  "type" text NOT NULL,
  "name" text NOT NULL,
  "source_year" text,
  PRIMARY KEY ("edition", "code")
)`,
  `CREATE INDEX IF NOT EXISTS "trademark_nice_snapshot_name_idx"
  ON "trademark_nice_snapshot" ("edition", "type", "name")`,
];

let total = 0;
for (const { edition, year } of snapshots) {
  const rows = readSnapshot(snapshotPath(edition, year));
  total += rows.length;
  for (let i = 0; i < rows.length; i += 500) {
    const values = rows.slice(i, i + 500).map((row) =>
      `(${edition}, ${year}, ${q(row.code)}, ${q(row.parentCode)}, ${q(row.type)}, ${q(row.name)}, ${q(row.version)})`
    ).join(",\n");
    chunks.push(
      `INSERT INTO "trademark_nice_snapshot" ("edition", "edition_year", "code", "parent_code", "type", "name", "source_year") VALUES\n${values}`,
    );
  }
}

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, chunks.join(";\n") + ";\n");
console.log(`wrote ${total} rows from ${snapshots.length} snapshots -> ${outPath}`);
