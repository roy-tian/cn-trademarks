import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";
import assert from "node:assert/strict";

const dataPath = join(import.meta.dirname, "..", "data", "nice.jsonl");
const sqlPath = join(
  import.meta.dirname,
  "..",
  "sql",
  "postgresql",
  "trademark_nice.sql",
);

interface NiceRow {
  code: string;
  parentCode: string | null;
  type: "class" | "group" | "item";
  name: string;
  version: string;
}

describe("cn-trademarks dataset", () => {
  const rows: NiceRow[] = existsSync(dataPath)
    ? readFileSync(dataPath, "utf-8")
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => JSON.parse(l) as NiceRow)
    : [];

  it("ships the dataset", () => {
    assert.ok(rows.length > 10000, `expected >10000 rows, got ${rows.length}`);
  });

  it("has all 45 classes", () => {
    const classes = rows.filter((r) => r.type === "class").map((r) => r.code);
    assert.equal(classes.length, 45);
    assert.equal(classes[0], "01");
    assert.equal(classes[44], "45");
  });

  it("keeps codes unique and sorted", () => {
    const codes = rows.map((r) => r.code);
    assert.equal(new Set(codes).size, codes.length);
    assert.deepEqual(
      [...codes].sort((a, b) => a.localeCompare(b)),
      codes,
    );
  });

  it("every row's parent chain is consistent with its code", () => {
    const groupCodes = new Set(
      rows.filter((r) => r.type === "group").map((r) => r.code),
    );
    for (const row of rows) {
      if (row.type === "class") {
        assert.equal(row.parentCode, null);
        assert.match(row.code, /^\d{2}$/);
      } else if (row.type === "group") {
        assert.equal(row.parentCode, row.code.slice(0, 2));
        assert.match(row.code, /^\d{4}$/);
      } else {
        // 项目编号在大类内全局顺序：前 2 位是大类，但前 4 位不一定是群组。
        assert.match(row.code, /^C?\d{6}$/);
        assert.ok(groupCodes.has(row.parentCode ?? ""));
        assert.equal(
          row.parentCode?.slice(0, 2),
          row.code.replace(/^C/, "").slice(0, 2),
        );
      }
    }
  });

  it("names are non-empty", () => {
    for (const row of rows) {
      assert.ok(row.name.trim().length > 0, `empty name at ${row.code}`);
    }
  });

  it("regenerable SQL contains INSERTs for every row", () => {
    const sql = readFileSync(sqlPath, "utf-8");
    assert.ok(sql.includes('INSERT INTO "trademark_nice"'));
    const tuples = sql.match(/\('[^']+',/g) ?? [];
    assert.equal(tuples.length, rows.length);
  });

  it("SQL ships a balanced-alias view for merged synonyms", () => {
    const sql = readFileSync(sqlPath, "utf-8");
    assert.match(sql, /CREATE OR REPLACE VIEW "trademark_nice_alias"/);
    assert.match(sql, /string_to_array\("name", '，'\)/);
    assert.match(sql, /WHERE "type" = 'item'/);
    // 括号平衡过滤：括号内含全角逗号的名称不产生残缺片段
    assert.match(
      sql,
      /AND length\(translate\("alias", '（\(', ''\)\) = length\(translate\("alias", '）\)', ''\)\)/,
    );
  });

  it("alias splitting resolves single-synonym lookups", () => {
    // 与 SQL 视图同逻辑：按全角逗号拆分 item 名称，只保留括号平衡的片段。
    const balanced = (a: string) =>
      (a.match(/[（(]/g) ?? []).length === (a.match(/[）)]/g) ?? []).length;
    const aliases = (row: NiceRow) =>
      row.name.split("，").map((p) => p.trim()).filter(balanced);
    const find = (a: string) =>
      rows
        .filter((r) => r.type === "item" && aliases(r).includes(a))
        .map((r) => r.code);
    // 「电池用防泡沫溶液，蓄电池用防泡沫溶液」两个别名均可精确命中
    assert.deepEqual(find("电池用防泡沫溶液"), ["010006"]);
    assert.deepEqual(find("蓄电池用防泡沫溶液"), ["010006"]);
    // 括号内含全角逗号：仅保留平衡片段，残缺片段不出现
    assert.deepEqual(find("传送带"), ["C070359"]);
    assert.deepEqual(find("棕编制品（包括棕箱"), []);
    for (const row of rows.filter((r) => r.type === "item"))
      for (const a of aliases(row))
        assert.ok(a.length > 0, `empty alias at ${row.code}`);
  });
});
