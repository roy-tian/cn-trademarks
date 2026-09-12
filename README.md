# cn-trademarks

中国《类似商品和服务区分表——基于尼斯分类第十三版（2026 文本）》数据集，扁平三层：

| type | code 形态 | parentCode | 说明 |
| --- | --- | --- | --- |
| `class` | 两位数字（`07`） | null | 大类 1–45 |
| `group` | 四位数字（`0701`） | 所属大类 | 类似群组 |
| `item` | 六位数字（`070479`）或 `C` + 六位（`C070012`） | 所属群组 | 商品/服务项目（C 前缀为中国增补） |

- 45 大类 / 492 类似群组 / 12,037 项目，共 12,517 行（详见 NOTICE.md 的来源与局限）；
- `data/nice.jsonl` — 规范数据，每行 `{ "code", "parentCode", "type", "name", "version" }`，按 code 排序；
- `sql/postgresql/trademark_nice.sql` — 批量 INSERT（`npm run generate:sql` 再生）；
- `tests/` — 行数与结构不变量钉死（45 类、编码唯一有序、父子链一致、名称非空）。

注意：项目编号是大类内全局顺序号，前 4 位**不一定**等于所属群组（如 010001 属于群组 0104）；
`parentCode` 来自区分表印刷版式，不要从编码推导。同码同义词行（如 090299 倾角计/坡度指示器）
聚合为一条，名称以全角逗号连接。

## 消费方

TFS backend（`@tfs/backend`）迁移经 `require.resolve("cn-trademarks/sql/postgresql/trademark_nice.sql")`
播种 `trademark_nice` 表（严格 INSERT 过滤，零插入即抛错）。

## 重新生成（官方发布文本版完整区分表时）

```bash
# 1. 视觉提取结果合并校验（提取产物默认在本仓库 extract/ 下，可用 argv 改路径）
node scripts/merge.ts <extractDir> <outJsonl>
# 2. 套用 NCL 修改内容（文本版 PDF 经 pdftotext -layout 产物）
node scripts/apply-revision.ts <revision.txt> [inJsonl] [outJsonl] [reportPath]
# 3. 生成 SQL
npm run generate:sql
npm test
```
