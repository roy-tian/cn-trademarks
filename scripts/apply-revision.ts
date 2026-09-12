/**
 * 把《NCL13-2026 中文版和区分表修改内容》文本（pdftotext -layout 产物）
 * 套用到 data/nice.jsonl 基础层（NCL12-2025），产出终版数据 + 未识别清单。
 *
 * 用法: node scripts/apply-revision.ts <revision.txt> [inJsonl] [outJsonl] [reportPath]
 *
 * 识别的修改形态（编码权威，名称失配仅报告）：
 *   增加：名称 CODE[, 名称 CODE…]      【由 XXXX 移入】等后缀忽略
 *   删除：名称 CODE
 *   CODE"旧名"改为"新名"（一条 bullet 内可多个，逗号分隔）
 *   NNNN Ø 类似群名称修改为"…"         （含 …… 的缩略标题跳过并报告）
 *   NNNN Ø 本类似群整体删除            （群组+其下项目全删）
 * 注释/标题类 bullet 不带项目编码，天然被 CODE 过滤；标题缩略（……）跳过。
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const revisionPath = process.argv[2];
const inPath = process.argv[3] ?? join(import.meta.dirname, "../data/nice.jsonl");
const outPath = process.argv[4] ?? inPath;
const reportPath =
  process.argv[5] ??
  join(import.meta.dirname, "../revision-report.txt");

if (!revisionPath) throw new Error("usage: apply-revision.ts <revision.txt>");

interface NiceRow {
  code: string;
  parentCode: string | null;
  type: "class" | "group" | "item";
  name: string;
  version: string;
}

const rows: NiceRow[] = readFileSync(inPath, "utf-8")
  .split("\n")
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l) as NiceRow);
const byCode = new Map(rows.map((r) => [r.code, r]));

const report: string[] = [];

// de-newline：换行只会打断名称/引号，不会引入语义；空格保留（后面统一剥离）。
const raw = readFileSync(revisionPath, "utf-8").replace(/\r/g, "");
const flat = raw.replace(/\n/g, " ");

// ---- bullets：按 Ø 切 ----
const bullets = flat
  .split("Ø")
  .map((b) => b.trim())
  .filter(Boolean);

const stripWs = (s: string) => s.replace(/\s+/g, "").replace(/^\*|\*$/g, "");

let added = 0;
let renamed = 0;
let deletedItems = 0;
let groupRenames = 0;
let groupDeletes = 0;

const ADD_ITEM = /^(?:C?\d{6})$/;
// name + 6 位编码 + 可选【…】注记 + 若干行尾上下文残片（下一群组号、页码、
// “标题/注释”等 1-4 位数字或词）——pdftotext -layout 会把它们粘在段尾。
const segmentRe =
  /^(.+?)\s*((?:C)?\d{6})(?:【[^】]*】)?(?:\s*(?:\d{1,4}|\d+\/\d+|标题|注释))*\s*$/;
const renameRe =
  /((?:C)?\d{6})\s*["“]([^"”]+)["”]\s*改为\s*["“]([^"”]+)["”]/g;

// ---- 群组整体删除 / 群组改名：需要编码与 Ø 的邻接关系，先在全文上做 ----
for (const match of flat.matchAll(/(\d{4})\s*Ø\s*本类似群整体删除/g)) {
  const group = match[1];
  const victims = rows.filter(
    (r) => r.code === group || r.parentCode === group,
  );
  if (victims.length === 0) {
    report.push(`整体删除群组 ${group}：基础层中不存在`);
    continue;
  }
  for (const victim of victims) byCode.delete(victim.code);
  groupDeletes++;
}

for (const match of flat.matchAll(
  /(\d{4})\s*Ø\s*类似群名称修改为\s*["“]([^"”]+)["”]/g,
)) {
  const [, group, name] = match;
  const clean = stripWs(name);
  if (!clean || clean.includes("……") || clean.includes("...")) {
    report.push(`群组 ${group} 改名含缩略，未套用：${clean}`);
    continue;
  }
  const row = byCode.get(group);
  if (!row) {
    report.push(`群组 ${group} 改名：基础层中不存在`);
    continue;
  }
  row.name = clean;
  row.version = "2026";
  groupRenames++;
}

// ---- item 级 bullet ----
for (const bullet of bullets) {
  // 去掉 bullet 开头可能残留的群组号/页码/类号上下文与“第X部分：”前缀。
  let body = bullet
    .replace(/^.*?(?=(标题|注释|增加|删除|本类|本类似群|类似群|[0-9C]))/, "")
    .replace(/^第[一二三四五六七八九十\d]+部分[：:]\s*/, "")
    .replace(/^第[一二三四五六七八九十\d]+自然段[：:]\s*/, "")
    .trim();

  const renameMatches = [...bullet.matchAll(renameRe)];
  for (const [, code, oldName, newName] of renameMatches) {
    const row = byCode.get(code);
    const cleanNew = stripWs(newName);
    if (!cleanNew) continue;
    if (!row || row.type !== "item") {
      report.push(`改名 ${code} "${stripWs(oldName)}"→"${cleanNew}"：基础层无此项目`);
      continue;
    }
    if (stripWs(row.name) !== stripWs(oldName)) {
      report.push(
        `改名 ${code} 名称失配：基础 "${row.name}" vs 修订 "${stripWs(oldName)}"（按修订套用）`,
      );
    }
    row.name = cleanNew;
    row.version = "2026";
    renamed++;
  }

  if (/^增加注/.test(body) || /^删除注/.test(body)) continue;
  if (/^增加[：:]/.test(body) || /^删除[：:]/.test(body)) {
    const isAdd = body.startsWith("增");
    // bullet 尾部可能粘着下一个上下文标记，截断之。
    body = body
      .replace(/^增加[：:]\s*/, "")
      .replace(/^删除[：:]\s*/, "")
      .replace(/\d+\/\d+$/, "") // 页码
      .trim();
    const segments = body.split(/[，,]/).map((s) => s.trim()).filter(Boolean);
    for (const segment of segments) {
      const match = segmentRe.exec(segment);
      if (!match) {
        // 非项目片段（注释文字等）——无编码，跳过；有编码但形态怪则报告。
        if (/(?:C)?\d{6}/.test(segment) && !/（第[一二三四五六七八九十\d]+类）/.test(segment)) {
          report.push(`${isAdd ? "增加" : "删除"} 段未解析：${segment}`);
        }
        continue;
      }
      // 名称里夹杂的孤立 1-2 位数字是排版残片（页码/类号），剥掉；
      // “3D 眼镜”这类字母数字粘连不受影响。
      const name = stripWs(match[1]).replace(
        /(?<![\w])\d{1,2}(?![\w])/g,
        "",
      );
      const code = match[2].toUpperCase();
      if (isAdd) {
        const existing = byCode.get(code);
        if (existing) {
          report.push(`增加 ${code} ${name}：基础层已存在 "${existing.name}"`);
          continue;
        }
        const digits = code.replace(/^C/, "");
        const parent = digits.slice(0, 4);
        if (!byCode.has(parent)) {
          report.push(`增加 ${code} ${name}：所属群组 ${parent} 不存在`);
          continue;
        }
        byCode.set(code, {
          code,
          parentCode: parent,
          type: "item",
          name,
          version: "2026",
        });
        added++;
      } else {
        const existing = byCode.get(code);
        if (!existing) {
          report.push(`删除 ${code} ${name}：基础层无此项目`);
          continue;
        }
        if (stripWs(existing.name) !== name) {
          report.push(
            `删除 ${code} 名称失配：基础 "${existing.name}" vs 修订 "${name}"（仍删除）`,
          );
        }
        byCode.delete(code);
        deletedItems++;
      }
    }
  }
}

// ---- 输出 ----
const finalRows = [...byCode.values()].sort((a, b) =>
  a.code.localeCompare(b.code),
);
writeFileSync(
  outPath,
  finalRows.map((r) => JSON.stringify(r)).join("\n") + "\n",
);
writeFileSync(
  reportPath,
  report.length ? report.join("\n") + "\n" : "(no findings)\n",
);
console.log(
  `+${added} ~${renamed}items -${deletedItems}items ~${groupRenames}groups -${groupDeletes}groups -> ${finalRows.length} rows`,
);
console.log(`report (${report.length} findings) -> ${reportPath}`);
