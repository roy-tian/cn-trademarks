import { readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readSnapshot, snapshotPath, snapshots } from "../scripts/snapshot-data.ts";

const expected = new Map([
  [10, { classes: 45, groups: 497, items: 10_253 }],
  [11, { classes: 45, groups: 503, items: 11_489 }],
  [12, { classes: 45, groups: 506, items: 11_908 }],
  [13, { classes: 45, groups: 492, items: 11_986 }],
]);

const editions = new Map(
  snapshots.map(({ edition, year }) => [edition, readSnapshot(snapshotPath(edition, year))]),
);
const legacy = new Map(
  readFileSync(join(import.meta.dirname, "../data/nice.jsonl"), "utf-8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      const row = JSON.parse(line) as { code: string; name: string };
      return [row.code, row] as const;
    }),
);

describe("complete NCL edition snapshots", () => {
  for (const { edition, year } of snapshots) {
    it(`ships and validates NCL(${edition}-${year})`, () => {
      const rows = editions.get(edition)!;
      const counts = expected.get(edition)!;
      for (const [type, count] of [
        ["class", counts.classes],
        ["group", counts.groups],
        ["item", counts.items],
      ] as const) {
        assert.equal(rows.filter((row) => row.type === type).length, count);
      }
      assert.ok(rows.every((row) => !row.version || Number(row.version) <= year));
    });
  }

  it("keeps reused codes and renumbered services edition-specific", () => {
    const row = (edition: number, code: string) =>
      editions.get(edition)!.find((record) => record.code === code);
    assert.equal(row(12, "C010254")?.name, "固化剂");
    assert.equal(row(13, "C010254")?.name, "椰子醛");
    assert.equal(row(12, "440092")?.name, "配镜服务");
    assert.equal(row(13, "440092"), undefined);
    assert.equal(row(13, "C440006")?.name, "配镜服务");
    assert.equal(row(13, "0748")?.name, "发电机，非陆地车辆用马达和引擎，马达和引擎零部件");
  });

  it("pairs class-28 and class-34 codes with the CN-table names", () => {
    const row = (edition: number, code: string) =>
      editions.get(edition)!.find((record) => record.code === code);
    // The TIPO 2026 sheet pairs these names with the adjacent code; the CN
    // text (agreed by editions 10-12) is authoritative.
    assert.equal(row(13, "280240")?.name, "聚会彩炮（聚会助兴道具）");
    assert.equal(row(13, "280242")?.name, "面泥（玩具）");
    assert.equal(row(13, "280243"), undefined);
    assert.equal(row(13, "280244")?.name, "回力镖");
    assert.equal(row(13, "280248")?.name, "游泳手蹼");
    assert.equal(row(13, "280252")?.name, "越野滑轮用滑行手杖");
    assert.equal(row(13, "340001")?.name, "火柴");
    assert.equal(row(13, "340002")?.name, "雪茄及香烟烟嘴上黄琥珀烟嘴头");
    // CN-text synonyms dropped by the bilateral sheet must survive.
    assert.equal(row(13, "010100")?.name, "纯碱，苏打灰");
    assert.equal(row(13, "010098")?.name, "电镀液，镀锌液");
    // 2026 renames that add a * cross-group marker keep it.
    assert.equal(row(13, "180043")?.name, "伞*");
    assert.equal(row(13, "420011")?.name, "建筑学服务*");
    assert.equal(row(12, "30")?.name.endsWith("冰（冻结的水）。"), true);
  });

  it("keeps audited OCR-sensitive names corrected", () => {
    const row = (edition: number, code: string) =>
      editions.get(edition)!.find((record) => record.code === code);
    const expectedNames = new Map([
      ["10/010013", "四氯乙烷"],
      ["10/010200", "(未发酵)葡萄汁澄清剂"],
      ["10/C010002", "三氧化硫"],
      ["10/C070362", "(管道)疏通挖泥车"],
      ["10/C070437", "水力发电设备"],
      ["11/C010002", "三氧化硫"],
      ["11/C010053", "己二酸"],
      ["11/C070362", "（管道）疏通挖泥车"],
      ["12/C010053", "己二酸"],
      ["12/C010111", "己醇"],
      ["12/C010112", "环己醇"],
      ["13/C010053", "己二酸"],
      ["13/C010111", "己醇"],
      ["13/C010112", "环己醇"],
    ]);
    for (const [key, name] of expectedNames) {
      const [edition, code] = key.split("/");
      assert.equal(row(Number(edition), code)?.name, name, key);
    }

    const legacyNames = new Map([
      ["050456", "医用草本提取物"],
      ["100326", "兽医用低温治疗设备"],
      ["170092", "非文具用、非化妆用、非医用、非家用自粘胶带"],
      ["170131", "O形密封圈"],
      ["180066", "手持女用阳伞"],
      ["210234", "瓷、陶瓷、陶土、赤陶、黏土或玻璃制艺术品"],
      ["210252", "瓷、陶瓷、陶土、赤陶、黏土或玻璃制半身像"],
      ["410095", "提供卡拉OK服务"],
      ["140066", "锇"],
      ["150032", "铙钹"],
      ["260022", "揿扣"],
      ["C010053", "己二酸"],
      ["C010111", "己醇"],
      ["C010112", "环己醇"],
      ["0748", "发电机，非陆地车辆用马达和引擎，马达和引擎零部件"],
      [
        "1001",
        "外科、医疗和兽医用仪器、器械、设备，不包括电子、核子、电疗、医疗用X光设备、器械及仪器",
      ],
      ["100007", "外科用剪"],
      ["180043", "伞*"],
      ["210045", "瓶*"],
      ["210289", "长颈瓶*"],
      ["110121", "淋浴器*"],
      ["420011", "建筑学服务*"],
    ]);
    for (const [code, name] of legacyNames) {
      assert.equal(legacy.get(code)?.name, name, `legacy ${code}`);
    }
  });

  it("seeds every row with an edition and indexes name lookup", () => {
    const sql = readFileSync(
      join(import.meta.dirname, "../sql/postgresql/trademark_nice_snapshots.sql"),
      "utf-8",
    );
    const tuples = sql.match(/^\((?:10|11|12|13), 20\d{2}, '/gm) ?? [];
    assert.equal(tuples.length, [...editions.values()].reduce((sum, rows) => sum + rows.length, 0));
    assert.ok(sql.includes('PRIMARY KEY ("edition", "code")'));
    assert.ok(sql.includes('("edition", "type", "name")'));
    // Spot-check that the committed SQL matches the JSONL it is generated
    // from (a stale regenerate would otherwise pass the count check above).
    assert.ok(sql.includes("(13, 2026, '280244', '2802', 'item', '回力镖', '2025')"));
    assert.ok(sql.includes("(13, 2026, '340001', '3403', 'item', '火柴', '2025')"));
    assert.ok(sql.includes("(10, 2016, '010013', '0102', 'item', '四氯乙烷', '2016')"));
  });
});
