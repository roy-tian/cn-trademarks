import { readFileSync } from "node:fs";
import { join } from "node:path";

export interface NiceRow {
  code: string;
  parentCode: string | null;
  type: "class" | "group" | "item";
  name: string;
  /** Legacy field: year of the source or latest revision, not the NCL edition. */
  version?: string;
}

export const snapshots = [
  { edition: 10, year: 2016 },
  { edition: 11, year: 2022 },
  { edition: 12, year: 2025 },
  { edition: 13, year: 2026 },
] as const;

export function snapshotPath(edition: number, year: number): string {
  return join(import.meta.dirname, `../data/snapshots/ncl${edition}-${year}.jsonl`);
}

export function readSnapshot(path: string): NiceRow[] {
  const rows = readFileSync(path, "utf-8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as NiceRow);
  validateSnapshot(rows, path);
  return rows;
}

export function validateSnapshot(rows: NiceRow[], label: string): void {
  const errors: string[] = [];
  const codes = new Set<string>();
  const classes = new Set<string>();
  const groups = new Set<string>();

  for (const row of rows) {
    if (codes.has(row.code)) errors.push(`duplicate code ${row.code}`);
    codes.add(row.code);
    if (!row.name?.trim()) errors.push(`empty name ${row.code}`);
    if (row.type === "class") {
      if (!/^\d{2}$/.test(row.code) || row.parentCode !== null) {
        errors.push(`invalid class ${row.code}`);
      }
      classes.add(row.code);
    } else if (row.type === "group") {
      if (!/^\d{4}$/.test(row.code) || row.parentCode !== row.code.slice(0, 2)) {
        errors.push(`invalid group ${row.code}`);
      }
      groups.add(row.code);
    } else if (row.type !== "item" || !/^C?\d{6}$/.test(row.code)) {
      errors.push(`invalid item ${row.code}`);
    }
  }

  if (classes.size !== 45) errors.push(`expected 45 classes, found ${classes.size}`);
  if (rows.filter((row) => row.type === "item").length < 10_000) {
    errors.push("expected at least 10,000 items");
  }
  for (let n = 1; n <= 45; n++) {
    const code = String(n).padStart(2, "0");
    if (!classes.has(code)) errors.push(`missing class ${code}`);
  }
  for (const row of rows) {
    if (row.type === "group" && !classes.has(row.parentCode ?? "")) {
      errors.push(`group ${row.code} has missing class ${row.parentCode}`);
    }
    if (row.type === "item") {
      if (!groups.has(row.parentCode ?? "")) {
        errors.push(`item ${row.code} has missing group ${row.parentCode}`);
      }
      if (row.parentCode?.slice(0, 2) !== row.code.replace(/^C/, "").slice(0, 2)) {
        errors.push(`item ${row.code} belongs to another class`);
      }
    }
  }
  for (let i = 1; i < rows.length; i++) {
    if (rows[i - 1].code.localeCompare(rows[i].code) > 0) {
      errors.push(`out of order: ${rows[i - 1].code} before ${rows[i].code}`);
      break;
    }
  }
  if (errors.length) {
    throw new Error(`${label}: ${errors.length} validation errors\n${errors.slice(0, 30).join("\n")}`);
  }
}
