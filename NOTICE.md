# NOTICE

《类似商品和服务区分表》© 国家知识产权局商标局；《尼斯分类》© 世界知识产权组织（WIPO）。本包汇编编码、名称及类似群归属，供分类检索使用；正式申报以相应年度的官方文本为准。

## 四份快照的来源

| 快照 | 中国完整文本 | 国际项目编码、简体名称及类似群交叉核验 |
| --- | --- | --- |
| NCL(10-2016) | [商标局 PDF 的互联网档案馆存档](https://web.archive.org/web/20161111093519id_/http://sbj.saic.gov.cn/sbsq/spfl/200902/W020161009303205832663.pdf)，文本层提取 | 同一 PDF 的项目表 |
| NCL(11-2022) | [商标局 PDF 的互联网档案馆存档](https://web.archive.org/web/20230127120218id_/https://sbj.cnipa.gov.cn/sbj/images/20221221.pdf)，扫描件 OCR | [台湾智慧财产局公布的两岸 NCL11-2022 ODS](https://www.tipo.gov.tw/wSite/public/Attachment/0/f1746433987373.ods) |
| NCL(12-2025) | [商标局 PDF](https://sbj.cnipa.gov.cn/sbj/sbsq/sphfwfl/200902/W020251111398307679571.pdf)，扫描件 OCR；提取时使用[完整镜像](https://download.s21i.co99.net/28635592/0/1/ABUIABA9GAAgpO36zAYouuTezwU.pdf) | [台湾智慧财产局公布的两岸 NCL12-2025 ODS](https://www.tipo.gov.tw/wSite/public/Attachment/005/f1759826070657.ods) |
| NCL(13-2026) | 原包的 `data/nice.jsonl` 作为中国增补项及大类、类似群基础 | [台湾智慧财产局公布的两岸 NCL13-2026 ODS](https://www.tipo.gov.tw/wSite/public/Attachment/005/f1779416658252.ods)；[商标局修订清单](https://sbj.cnipa.gov.cn/sbj/sbsq/sphfwfl/200902/W020251226550778869452.pdf) |

2025 镜像与商标局 PDF 的互联网档案馆存档前 5 MiB 逐字节相同；档案馆当次只保存了这 5 MiB，镜像提供了完整 274 页。2016 PDF 有少量文本层顺序错误和一个五位 C 编号，已在 `scripts/extract-2016.py` 中逐项修正。2022、2025 的类别、群组和 C 编号来自扫描件 OCR；国际编号、名称及群组由对照表核验。OCR 漏掉的连续 C 编号按扫描原页或原包中未变的 2025 项目补入，所用清单保留在 `scripts/build-snapshots.py` 中。

本版另已修正审计发现的 OCR/版式伪影：提取器只删除完整的部分标记（如 `（一）`），保留名称中的中文数字和括号；2016、2022 扫描结果及原单版中的已确认字误已同步到 JSON 和 SQL。两岸 NCL13-2026 对照表在第 28 类 280240–280252 段将名称与相邻编码错行、并互换 340001/340002 的名称，NCL13 快照对这些编码以中国文本为准（见 `scripts/build-snapshots.py` 的 `ods2026_untrusted`）。扫描件中的中国增补名称仍可能存在未被当前交叉来源覆盖的个别 OCR 字误。

提取时三份完整 PDF 的 SHA-256 分别为：2016 `4caf43edea298931949478a8a67c130b23287360972159e7b6b02f1d234020f7`；2022 `8461a5788909db6f66dd5ccebfc4cc4d440952810aec3025aaed45046d052f2c`；2025 `08446cfbfe8b7117e1ff057d278f8404b92d841aa1f52009569ec9ae2bf7d755`。

同一编码在不同类似群重复列出或有多个同义名称时，本包聚合为一条，以全角逗号连接名称，`parentCode` 取其中一个所属群组。原书中的注释、跨类似群保护关系及废止群组的法律含义未结构化。扫描件中的中国增补名称仍可能存在个别 OCR 字误；结构校验不能替代逐字与官方原页核对。

## 原单版文件

`data/nice.jsonl` 和 `sql/postgresql/trademark_nice.sql` 继续保留初始 NCL13-2026 单版数据，供现有消费者使用；行数与编码不变，但已修正其中的确认提取错误（名称字误、群组 0748/1001 标题及丢失的 `*` 标记，清单在 `scripts/apply-revision.ts` 的 `OCR_FIXES`），既有数据库需按新文件 UPDATE 对应行。该文件基于 2025 扫描件视觉识别和 2026 修订清单生成，`version` 表示条目来源年份（2025 或 2026），不是完整的两个历史版本；扫描基线的行级配对漂移意味着个别国际项目名称未经第二来源核验。新 NCL13 快照对国际项目采用两岸对照表核验，因此与原单版文件存在少量名称、编号差异（如 `160142`/`160412` 的配对两源不一致，以官方文本复核为准）。
