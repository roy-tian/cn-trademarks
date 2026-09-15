# cn-trademarks

中国《类似商品和服务区分表》的四份完整快照。每个尼斯大版取最后一个年度文本：

| 尼斯版本 | 文件 | 大类 | 类似群组 | 项目 |
| --- | --- | ---: | ---: | ---: |
| NCL(10-2016) | `data/snapshots/ncl10-2016.jsonl` | 45 | 497 | 10,253 |
| NCL(11-2022) | `data/snapshots/ncl11-2022.jsonl` | 45 | 503 | 11,489 |
| NCL(12-2025) | `data/snapshots/ncl12-2025.jsonl` | 45 | 506 | 11,908 |
| NCL(13-2026) | `data/snapshots/ncl13-2026.jsonl` | 45 | 492 | 11,986 |

每行是 `{ "code", "parentCode", "type", "name", "version" }`，按编码排序。`type` 分为 `class`（两位大类编号）、`group`（四位类似群编号）、`item`（六位编号或 `C` 加六位中国增补编号）。**快照所属版本由文件名和 SQL 的 `edition` 列确定**。`version`（SQL 的 `source_year`）含义按版本而异：NCL13-2026 沿用旧含义（条目文本的来源/最后修订年份，2025 或 2026），NCL10/11/12 因缺乏逐年修订记录统一填快照年份，不可跨版本比较。不同版本的同一编号可能有不同名称或归属，例如 `C010254` 在 2025 年为“固化剂”，在 2026 年为“椰子醛”。

`data/nice.jsonl` 和 `sql/postgresql/trademark_nice.sql` 保留原有 2026 单版数据及播种方式，供现有消费者兼容使用。注意：本版修正了原文件中的确认提取错误（14 个项目名称字误，以及群组 0748/1001 的标题、100007 的粘连名称、5 个项目丢失的 `*` 跨类似群标记），行数与编码不变，但名称有变——已播种的数据库需要按新文件 UPDATE 这些编码（严格 INSERT 过滤不会更新既有行）。新快照根据历年官方文本和两岸分类对照表校验，因此与原单版文件在少量编码和名称上不同；新消费者应使用 `data/snapshots/` 和 `sql/postgresql/trademark_nice_snapshots.sql`。来源及提取局限见 [NOTICE.md](NOTICE.md)。

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

同码同义词仍以全角逗号合并为一个 `name`。只输入其中一个别名做精确匹配时可能查不到，调用方可按需做包含检索或建立别名表。项目编号前四位**不一定**是所属类似群；应使用 `parentCode`，不要从编码推导。

## 重新生成

四份快照从官方 PDF、两岸尼斯分类 ODS 对照表及旧数据生成。先按 [NOTICE.md](NOTICE.md) 的链接下载原件；2016 PDF 有文本层，2022 和 2025 PDF 为扫描件。扫描件提取需要 Python、PyMuPDF、NumPy 和 `rapidocr-onnxruntime`。

```bash
python scripts/extract-2016.py <2016.pdf> data/snapshots/ncl10-2016.jsonl
python scripts/ocr-scanned.py 2022 <2022.pdf> <2022-ocr.jsonl>
python scripts/ocr-scanned.py 2025 <2025.pdf> <2025-ocr.jsonl> 29
python scripts/extract-scanned.py 2022 <2022-ocr.jsonl> <2022-draft.jsonl>
python scripts/extract-scanned.py 2025 <2025-ocr.jsonl> <2025-draft.jsonl>
python scripts/build-snapshots.py <2022-draft.jsonl> <2025-draft.jsonl> <2022.ods> <2025.ods> <2026.ods> data/snapshots
npm run generate:snapshots
npm test
```

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
