-- v0.1.0 -> v0.1.1 数据修正：22 行仅 name 变化
--（14 个 OCR 字误、群组 0748/1001 标题、100007 粘连名称、5 个补回的 * 跨类似群标记）。
-- 用于已按 v0.1.0 的 trademark_nice.sql 播种的数据库：严格 INSERT 过滤不会更新既有行，
-- 需执行本文件同步（幂等，可重复执行）。修正清单见 scripts/apply-revision.ts 的 OCR_FIXES。
UPDATE "trademark_nice" SET "name" = 'O形密封圈' WHERE "code" = '170131';
UPDATE "trademark_nice" SET "name" = '伞*' WHERE "code" = '180043';
UPDATE "trademark_nice" SET "name" = '兽医用低温治疗设备' WHERE "code" = '100326';
UPDATE "trademark_nice" SET "name" = '医用草本提取物' WHERE "code" = '050456';
UPDATE "trademark_nice" SET "name" = '发电机，非陆地车辆用马达和引擎，马达和引擎零部件' WHERE "code" = '0748';
UPDATE "trademark_nice" SET "name" = '外科、医疗和兽医用仪器、器械、设备，不包括电子、核子、电疗、医疗用X光设备、器械及仪器' WHERE "code" = '1001';
UPDATE "trademark_nice" SET "name" = '外科用剪' WHERE "code" = '100007';
UPDATE "trademark_nice" SET "name" = '己二酸' WHERE "code" = 'C010053';
UPDATE "trademark_nice" SET "name" = '己醇' WHERE "code" = 'C010111';
UPDATE "trademark_nice" SET "name" = '建筑学服务*' WHERE "code" = '420011';
UPDATE "trademark_nice" SET "name" = '手持女用阳伞' WHERE "code" = '180066';
UPDATE "trademark_nice" SET "name" = '提供卡拉OK服务' WHERE "code" = '410095';
UPDATE "trademark_nice" SET "name" = '揿扣' WHERE "code" = '260022';
UPDATE "trademark_nice" SET "name" = '淋浴器*' WHERE "code" = '110121';
UPDATE "trademark_nice" SET "name" = '环己醇' WHERE "code" = 'C010112';
UPDATE "trademark_nice" SET "name" = '瓶*' WHERE "code" = '210045';
UPDATE "trademark_nice" SET "name" = '瓷、陶瓷、陶土、赤陶、黏土或玻璃制半身像' WHERE "code" = '210252';
UPDATE "trademark_nice" SET "name" = '瓷、陶瓷、陶土、赤陶、黏土或玻璃制艺术品' WHERE "code" = '210234';
UPDATE "trademark_nice" SET "name" = '铙钹' WHERE "code" = '150032';
UPDATE "trademark_nice" SET "name" = '锇' WHERE "code" = '140066';
UPDATE "trademark_nice" SET "name" = '长颈瓶*' WHERE "code" = '210289';
UPDATE "trademark_nice" SET "name" = '非文具用、非化妆用、非医用、非家用自粘胶带' WHERE "code" = '170092';
