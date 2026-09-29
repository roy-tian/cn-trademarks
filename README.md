# cn-trademarks

中国《类似商品和服务区分表》的四份完整快照，只依据国家知识产权局商标局发布的中文文本生成。每个尼斯大版取最后一个年度文本：

| 尼斯版本 | 文件 | 大类 | 类似群组 | 项目 |
| --- | --- | ---: | ---: | ---: |
| NCL(10-2016) | `data/snapshots/ncl10-2016.jsonl` | 45 | 497 | 10,253 |
| NCL(11-2022) | `data/snapshots/ncl11-2022.jsonl` | 45 | 503 | 11,493 |
| NCL(12-2025) | `data/snapshots/ncl12-2025.jsonl` | 45 | 506 | 11,908 |
| NCL(13-2026) | `data/snapshots/ncl13-2026.jsonl` | 45 | 505 | 11,986 |

每行是 `{ "code", "parentCode", "type", "name", "version" }`，按编码排序。`type` 分为 `class`（两位大类编号）、`group`（四位类似群编号）、`item`（六位编号或 `C` 加六位中国增补编号）。**快照所属版本由文件名和 SQL 的 `edition` 列确定**。`version`（SQL 的 `source_year`）含义按版本而异：NCL13-2026 中为该行最后修订年份——被 2026 修订清单改动过的行（增加、删除、改名、改编号、移入其他类似群，类别和群组标题的修改）为 2026，其余为 2025；NCL10/11/12 因缺乏逐年修订记录统一填快照年份，不可跨版本比较。不同版本的同一编号可能有不同名称或归属，例如 `C010254` 在 2025 年为“固化剂”，在 2026 年为“椰子醛”。

`data/nice.jsonl` 和 `sql/postgresql/trademark_nice.sql` 保留原有 2026 单版数据及播种方式，供现有消费者兼容使用。注意：本版修正了原文件中的确认提取错误（14 个项目名称字误，以及群组 0748/1001 的标题、100007 的粘连名称、5 个项目丢失的 `*` 跨类似群标记），行数与编码不变，但名称有变——已播种的数据库可执行 `sql/postgresql/trademark_nice_fixes_v0.1.1.sql`（22 条幂等 UPDATE）同步；严格 INSERT 过滤不会更新既有行。新快照只依据商标局发布的历年中文文本及 NCL13 修订清单生成，与原单版文件在少量编码、名称、同义词和类似群归属上不同（见 NOTICE）；新消费者应使用 `data/snapshots/` 和 `sql/postgresql/trademark_nice_snapshots.sql`。来源及提取局限见 [NOTICE.md](NOTICE.md)。

## PostgreSQL 使用

`sql/postgresql/trademark_nice_snapshots.sql` 创建独立的 `trademark_nice_snapshot` 表并插入四版数据。主键是 `(edition, code)`，名称检索索引是 `(edition, type, name)`。名称可能对应多个编号，查询应返回列表；默认最新版本时指定 `edition = 13`。

现有 TFS 后端仍消费原单版 SQL；使用四版数据时需在下游迁移中执行新文件的建表、索引和插入语句，并将查询切换到新表。

```sql
SELECT code, name, parent_code
FROM trademark_nice_snapshot
WHERE edition = 13 AND type = 'item' AND name = '配镜服务'
ORDER BY code;

SELECT name, parent_code, type
FROM trademark_nice_snapshot
WHERE edition = 12 AND code = '440092';
```

同码同义词仍以全角逗号合并为一个 `name`。两份 SQL 各附带别名视图（`trademark_nice_alias` / `trademark_nice_snapshot_alias`），把 item 的合并名称拆成独立别名行，单一别名可直接精确匹配：

```sql
SELECT code, parent_code
FROM trademark_nice_snapshot_alias
WHERE edition = 13 AND alias = '计量仪表';  -- 090138「计数器，计量仪表」
```

视图仅拆分 `type = 'item'`（类别和群组标题含合法全角逗号）；别名保留 `*` 跨类似群标记；只输出括号平衡的完整别名——括号内含全角逗号的名称（如 `C070359`、`C200016`）不产生残缺片段，其原名称仍可对主表 `name` 做包含检索。项目编号前四位**不一定**是所属类似群；应使用 `parentCode`，不要从编码推导。

## 重新生成

四份快照只从商标局发布的中文原件及原单版文件生成。先按 [NOTICE.md](NOTICE.md) 的链接下载原件；2016 PDF 和 NCL13 修订清单有文本层，2022 和 2025 PDF 为扫描件。扫描件提取需要 Python、PyMuPDF、NumPy 和 `rapidocr-onnxruntime`（提取时为 1.4.4）。扫描件各识别三遍（两种倍率整页识别，再对漏行处补识别），由 `extract-scanned.py` 合并。

```bash
python scripts/extract-2016.py <2016.pdf> data/snapshots/ncl10-2016.jsonl
python scripts/extract-revision.py <ncl13-revision.pdf> scripts/ncl13-2026-revision.tsv
python scripts/ocr-scanned.py 2022 <2022.pdf> <2022-a.jsonl> 1 1.3
python scripts/ocr-scanned.py 2022 <2022.pdf> <2022-b.jsonl> 1 1.6
python scripts/ocr-scanned.py --gaps 2022 <2022.pdf> <2022-c.jsonl> <2022-a.jsonl> <2022-b.jsonl>
python scripts/ocr-scanned.py 2025 <2025.pdf> <2025-a.jsonl> 29 1.3
python scripts/ocr-scanned.py 2025 <2025.pdf> <2025-b.jsonl> 29 1.6
python scripts/ocr-scanned.py --gaps 2025 <2025.pdf> <2025-c.jsonl> <2025-a.jsonl> <2025-b.jsonl>
python scripts/extract-scanned.py 2022 <2022-a.jsonl> <2022-b.jsonl> <2022-c.jsonl> <2022-draft.jsonl>
python scripts/extract-scanned.py 2025 <2025-a.jsonl> <2025-b.jsonl> <2025-c.jsonl> <2025-draft.jsonl>
python scripts/build-snapshots.py <2022-draft.jsonl> <2025-draft.jsonl> data/snapshots
npm run generate:snapshots
npm test
```

`build-snapshots.py` 不单独采信任何 OCR 文字：无法由其他来源确认的名称会列出待核对，逐条对照原页图像后记入脚本中的 `NAMES`、`VERIFIED`、`TITLES`（`--review <file>` 可导出全部待核对项）。

单版文件（`data/nice.jsonl` → `sql/postgresql/trademark_nice.sql`）的再生成流程未变，仍从仓库外提取产物出发（从仓库根目录运行所有命令）：

```bash
# 1. 视觉提取结果合并校验（提取产物默认在本仓库 extract/ 下，可用 argv 改路径）
node scripts/merge.ts <extractDir> <outJsonl>
# 2. 套用 NCL 修改内容（文本版 PDF 经 pdftotext -layout 产物；
#    OCR_FIXES 修正表在该步骤末尾套用，防止重建时重新引入已修正的字误）
node scripts/apply-revision.ts <revision.txt> [inJsonl] [outJsonl] [reportPath]
# 3. 生成 SQL
npm run generate:sql
```
