import { readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readSnapshot, snapshotPath, snapshots } from "../scripts/snapshot-data.ts";

const expected = new Map([
  [10, { classes: 45, groups: 497, items: 10_253 }],
  [11, { classes: 45, groups: 503, items: 11_493 }],
  [12, { classes: 45, groups: 506, items: 11_908 }],
  [13, { classes: 45, groups: 505, items: 11_986 }],
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
    // Moved and multiply printed items take their lowest group.
    assert.equal(row(12, "090304")?.parentCode, "0910");
    assert.equal(row(13, "090304")?.parentCode, "0913");
    assert.equal(row(13, "370179")?.parentCode, "3707");
    assert.equal(row(13, "0305"), undefined);
    assert.equal(row(13, "1011")?.name, "眼镜及附件");
  });

  it("pairs class-28 and class-34 codes with the CN-table names", () => {
    const row = (edition: number, code: string) =>
      editions.get(edition)!.find((record) => record.code === code);
    // Regression pins for names the 0.1.x releases once paired with the
    // adjacent code; the CN text of editions 10-12 agrees on these.
    assert.equal(row(13, "280240")?.name, "聚会彩炮（聚会助兴道具）");
    assert.equal(row(13, "280242")?.name, "面泥（玩具）");
    assert.equal(row(13, "280243"), undefined);
    assert.equal(row(13, "280244")?.name, "回力镖");
    assert.equal(row(13, "280248")?.name, "游泳手蹼");
    assert.equal(row(13, "280252")?.name, "越野滑轮用滑行手杖");
    assert.equal(row(13, "340001")?.name, "火柴");
    assert.equal(row(13, "340002")?.name, "雪茄及香烟烟嘴上黄琥珀烟嘴头");
    // Synonyms keep the order they are printed in ("苏打灰010100，纯碱010100").
    assert.equal(row(13, "010100")?.name, "苏打灰，纯碱");
    assert.equal(row(13, "010098")?.name, "镀锌液，电镀液");
    // 2026 renames that add a * cross-group marker keep it.
    assert.equal(row(13, "180043")?.name, "伞*");
    assert.equal(row(13, "420011")?.name, "建筑学服务*");
    assert.equal(row(12, "30")?.name.endsWith("冰（冻结的水）。"), true);
  });

  it("applies every operation of the CN 2026 revision list to NCL13", () => {
    const ops = readFileSync(join(import.meta.dirname, "../scripts/ncl13-2026-revision.tsv"), "utf-8")
      .trim()
      .split("\n")
      .slice(1)
      .map((line) => {
        const [group, op, code, name, next] = line.split("\t");
        return { group, op, code, name, next };
      });
    assert.ok(ops.length > 300);
    const e12 = new Map(editions.get(12)!.map((r) => [r.code, r]));
    const e13 = new Map(editions.get(13)!.map((r) => [r.code, r]));
    const names = (code: string) => e13.get(code)?.name.split("，") ?? [];
    const created = new Set(ops.filter((o) => o.op === "add").map((o) => o.code));
    // Codes the revision keeps printing somewhere (300070: deleted in 3018,
    // renamed in 3016).
    const kept = new Set(ops.filter((o) => o.op === "add" || o.op === "rename").map((o) => o.code));
    for (const o of ops) {
      const label = `${o.group} ${o.op} ${o.code} ${o.name}`;
      if (o.op === "add") assert.ok(names(o.code).includes(o.name), label);
      if (o.op === "rename") assert.ok(names(o.code).includes(o.next), label);
      if (o.op === "renumber") {
        assert.ok(e13.get(o.next)?.name.includes(o.name), label);
        // Only the named printing moves (090381 keeps 避雷针).
        if (!created.has(o.code)) assert.ok(!names(o.code).includes(o.name), label);
      }
      if (o.op === "delete" && !kept.has(o.code) && e12.get(o.code)?.name === o.name) {
        assert.equal(e13.get(o.code), undefined, label); // its only printing is gone
      }
      if (o.op === "group-rename" || o.op === "group-new") assert.equal(e13.get(o.group)?.name, o.next);
      if (o.op === "group-delete") {
        assert.equal(e13.get(o.group), undefined, label);
        assert.ok(editions.get(13)!.every((r) => r.parentCode !== o.group), label);
      }
    }
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
      // RapidOCR drops 鞣 and misreads element names; checked on the page.
      ["12/01", "用于工业、科学、摄影、农业、园艺和林业的化学品；未加工人造合成树脂，未加工塑料物质；灭火和防火用合成物；淬火和焊接用制剂；鞣制动物皮毛用物质；工业用黏合剂；油灰及其他膏状填料；堆肥，肥料，化肥；工业和科学用生物制剂。"],
      ["12/010018", "锕"],
      ["12/0114", "鞣料及皮革用化学品"],
      ["12/380060", "电话答录机出租"],
      ["12/3609", "典当"],
      ["12/360031", "典当经纪"],
      // 2025 prints 纸制或塑料制食品袋 as 160410; WIPO numbers it 160409.
      ["12/160409", "纸制或塑料制食品袋"],
      ["12/160410", "聚会用纸制装饰品"],
      // The revision adds 绳绒织物棒 as 160142 (墨水*); WIPO numbers it 160412.
      ["13/160142", "墨水*"],
      ["13/160412", "制手工艺品用绳绒织物棒"],
      // "“避雷器”编号由090381改为090955" moves one printing only.
      ["13/090381", "避雷针"],
      ["13/090955", "避雷器"],
      // Synonyms of one printing each, added and deleted per group.
      ["13/210191", "肥皂碟"],
      ["13/300070", "蛋糕用调味品"],
      ["13/090138", "计数器，计量仪表"],
    ]);
    for (const [key, name] of expectedNames) {
      const [edition, code] = key.split("/");
      assert.equal(row(Number(edition), code)?.name, name, key);
    }
    // Every other name, printing and title checked on the page images
    // (NAMES, VERIFIED and TITLES in scripts/build-snapshots.py).
    const pageChecked = new Map([
      ["11/01", "用于工业、科学、摄影、农业、园艺和林业的化学品；未加工人造合成树脂，未加工塑料物质；灭火和防火用合成物；淬火和焊接用制剂；鞣制动物皮毛用物质；工业用黏合剂；油灰及其他膏状填料；堆肥，肥料，化肥；工业和科学用生物制剂。"],
      ["11/010728", "制食品用植物提取物，食品工业用植物提取物"],
      ["11/020005", "食用色素，食品用着色剂"],
      ["11/020113", "羰基（木头防腐剂）"],
      ["11/020134", "木地板面漆"],
      ["11/03", "不含药物的化妆品和梳洗用制剂；不含药物的牙膏；香料，香精油；洗衣用漂白剂及其他物料；清洁、擦亮、去渍及研磨用制剂。"],
      ["11/040065", "工业用菜油，工业用菜籽油"],
      ["11/060011", "钢管"],
      ["11/060014", "金属喷头"],
      ["11/060021", "金属喷嘴"],
      ["11/060047", "金属装甲板"],
      ["11/060058", "绳索用金属套管"],
      ["11/060208", "金属制帐篷地钉"],
      ["11/090113", "非人工呼吸用呼吸面罩"],
      ["11/090755", "安全令牌（加密装置）"],
      ["11/090757", "掌上电脑用套"],
      ["11/090778", "科学研究用具有人工智能的人形机器人"],
      ["11/090780", "电子香烟用电池"],
      ["11/090804", "移动电话用可下载图像"],
      ["11/090881", "移动电话和智能手机专用支架"],
      ["11/090885", "色盲矫正眼镜"],
      ["11/090896", "移动电话和智能手机专用仪表板防滑垫"],
      ["11/100160", "医用气雾剂分配器"],
      ["11/100276", "吸入器用分隔器"],
      ["11/100304", "超声波面部美容治疗仪"],
      ["11/11", "照明、加热、冷却、蒸汽发生、烹饪、干燥、通风、供水以及卫生用装置和设备。"],
      ["11/110352", "家用电动米糕机"],
      ["11/110359", "医学贮存用冰箱、冷却装置和冰柜"],
      ["11/110370", "烟雾机"],
      ["11/110380", "水过滤装置用过滤器，水过滤设备用膜"],
      ["11/120129", "铁路冷藏货车"],
      ["11/120154", "挡风玻璃，风挡"],
      ["11/120249", "野营车，房车"],
      ["11/120279", "无人驾驶汽车，自动驾驶汽车"],
      ["11/120306", "救援用雪橇"],
      ["11/120326", "两栖车"],
      ["11/120331", "运输用船型雪橇"],
      ["11/1207", "畜力车辆，雪橇"],
      ["11/140182", "帽子用装饰针"],
      ["11/140183", "贵金属制雕塑纪念杯"],
      ["11/1402", "贵金属盒"],
      ["11/160224", "纸张压摺器（办公用品）"],
      ["11/180144", "手提箱用分装收纳袋，行李箱用成套收纳袋"],
      ["11/200045", "仿制玳瑁"],
      ["11/200084", "非金属制固定式毛巾分配器"],
      ["11/200143", "运输物品用带盖篮"],
      ["11/200360", "服装用塑料或橡胶制缝制标签"],
      ["11/210379", "制刷用猪鬃"],
      ["11/210385", "厨房用研钵"],
      ["11/210396", "烹饪网袋（非微波炉用）"],
      ["11/210424", "售时为空的智能药瓶"],
      ["11/210430", "售时为空的化妆用印章"],
      ["11/210432", "自动开闭的垃圾桶"],
      ["11/210433", "声波震动发梳"],
      ["11/210437", "分菜匙"],
      ["11/22", "绳索和细绳；网；帐篷和防水遮布；纺织品或合成材料制遮篷；帆；运输和贮存散装物用麻袋；衬垫和填充材料（纸或纸板、橡胶、塑料制除外）；纺织用纤维原料及其替代品。"],
      ["11/220045", "软百叶帘用梯形带"],
      ["11/220068", "运输和贮存散装物用麻袋"],
      ["11/250178", "空手道服"],
      ["11/250179", "柔道服"],
      ["11/260143", "帽子用非装饰别针"],
      ["11/280030", "草地滚球比赛用球"],
      ["11/290048", "食品用果冻"],
      ["11/290068", "肉汁"],
      ["11/290072", "奶饮料（以奶为主）"],
      ["11/290176", "低脂土豆片，低脂炸土豆片"],
      ["11/300293", "裹巧克力的炸土豆片"],
      ["11/32", "啤酒；无酒精饮料；矿泉水和汽水；水果饮料及果汁；糖浆及其他用于制作无酒精饮料的制剂。"],
      ["11/320008", "制作无酒精饮料用配料"],
      ["11/320009", "制作饮料用无酒精原汁"],
      ["11/320013", "制作加气水用配料，制作碳酸水用配料"],
      ["11/320017", "气泡水"],
      ["11/320063", "制作饮料用淀粉基干混料"],
      ["11/34", "烟草和烟草代用品；香烟和雪茄；电子香烟和吸烟者用口腔雾化器；烟具；火柴。"],
      ["11/340040", "电子香烟烟液"],
      ["11/3407", "电子香烟及其部件"],
      ["11/350172", "组织商业活动"],
      ["11/36", "金融，货币和银行服务；保险服务；不动产事务。"],
      ["11/370156", "非研究目的的废址挖掘"],
      ["11/370157", "通过远程监控系统对电梯（升降机）进行保养"],
      ["11/390076", "提供关于贮藏服务的信息"],
      ["11/390094", "电子数据或文件载体的物理贮存"],
      ["11/390123", "停车场服务"],
      ["11/390126", "为运输目的对人员和货物进行定位和追踪"],
      ["11/400133", "定制生产小船，定制生产游艇"],
      ["11/400136", "航空器的定制装配，定制生产航空器"],
      ["11/410064", "提供关于消遣活动的信息"],
      ["11/410220", "柔道训练"],
      ["11/410239", "提供培训和教育考试（教育认证服务）"],
      ["11/410242", "组织娱乐活动"],
      ["11/410246", "举办娱乐活动"],
      ["11/420193", "测量"],
      ["11/420268", "用于制图或热成像的无人机测量服务"],
      ["11/440166", "树木修剪"],
      ["11/440250", "为残疾人提供服务性动物"],
      ["11/45", "法律服务；为有形财产和个人提供实体保护的安全服务；由他人提供的为满足个人需要的私人和社会服务。"],
      ["11/450232", "遛狗服务"],
      ["11/450257", "定位和追踪失踪人员和财产"],
      ["11/C090143", "行车记录仪"],
      ["12/010404", "预防小麦枯萎病的化学制剂，预防小麦黑穗病的化学制剂"],
      ["12/010710", "厩肥"],
      ["12/020113", "木头防腐用羰基化合物"],
      ["12/03", "不含药物的化妆品和梳洗用制剂；不含药物的牙膏；香料，香精油；洗衣用漂白剂及其他物料；清洁、擦亮及研磨用制剂。"],
      ["12/030099", "醚类香精"],
      ["12/030110", "香叶醇"],
      ["12/030159", "萜烯烃（香精油）"],
      ["12/030226", "香橼香精油"],
      ["12/030270", "芳香疗法用香精油"],
      ["12/030274", "芳香疗法用香精油制乳霜"],
      ["12/05", "药品，医用和兽医用制剂；医用卫生制剂；医用或兽医用营养食物和物质，婴儿食品；人用和动物用膳食补充剂；膏药，绷敷材料；填塞牙孔用料，牙科用蜡；消毒剂；消灭有害动物制剂；杀真菌剂，除莠剂。"],
      ["12/050222", "治小麦枯萎病的化学制剂，治小麦黑穗病的化学制剂"],
      ["12/060232", "金属蓄水池，（储液或储气用）金属容器"],
      ["12/060260", "金属制楣窗"],
      ["12/070610", "味噌制造机"],
      ["12/070611", "制备饮料用机械臂"],
      ["12/070622", "舷外马达"],
      ["12/08", "手工具和器具（手动的）；刀、叉和匙餐具；除火器外的随身武器；剃刀。"],
      ["12/080172", "撞锤（手工具），撞杵（手工具）"],
      ["12/080236", "剔肉刀，切碎刀，剁肉刀"],
      ["12/09", "科学、研究、导航、测量、摄影、电影、视听、光学、衡具、量具、信号、侦测、测试、检验、救生和教学用装置及仪器；处理、开关、转换、积累、调节或控制电的配送或使用的装置和仪器；录制、传送、重放或处理声音、影像或数据的装置和仪器；已录制和可下载的媒体，计算机软件，录制和存储用空白的数字或模拟介质；投币启动设备用机械装置；收银机，计算设备；计算机和计算机外围设备；潜水服，潜水面罩，潜水用耳塞，潜水和游泳用鼻夹，潜水员手套，潜水呼吸器；灭火设备。"],
      ["12/090876", "伺服电机用电子控制器"],
      ["12/090885", "色觉缺陷矫正眼镜"],
      ["12/090886", "具有超声波清洗功能的隐形眼镜盒"],
      ["12/10", "外科、医疗、牙科和兽医用仪器及器械；假肢，假眼和假牙；矫形用物品；缝合材料；残疾人专用治疗装置；按摩器械；婴儿护理用器械、器具及用品；性生活用器械、器具及用品。"],
      ["12/100182", "医用吸入剂给药装置"],
      ["12/100257", "氢吸入器"],
      ["12/100290", "植入式避孕器"],
      ["12/100305", "震颤患者用勺"],
      ["12/120296", "铰接式公共汽车用铰接箱"],
      ["12/120306", "救援用雪橇"],
      ["12/120331", "运输用船型雪橇"],
      ["12/1207", "畜力车辆，雪橇"],
      ["12/160224", "纸张压摺器（办公用品）"],
      ["12/170131", "O形密封圈"],
      ["12/190179", "非金属制楣窗"],
      ["12/190269", "玩耍用沙"],
      ["12/200045", "仿制玳瑁"],
      ["12/200084", "非金属制毛巾分配器"],
      ["12/210103", "烹饪用模具"],
      ["12/210379", "制刷用猪鬃"],
      ["12/210384", "厨房用杵"],
      ["12/210442", "纸巾盒套"],
      ["12/210470", "浴室用长柄水瓢"],
      ["12/220114", "猪鬃*"],
      ["12/250148", "班丹纳方绸（围巾）"],
      ["12/26", "花边，编带和刺绣品，缝纫用饰带和蝴蝶结；纽扣，领钩扣，饰针和缝针；人造花；发饰；假发。"],
      ["12/29", "肉，鱼，家禽和野味；肉汁；腌渍、冷冻、干制及煮熟的水果和蔬菜；果冻，果酱，蜜饯；蛋；奶，奶酪，黄油，酸奶和其他奶制品；食用油和油脂。"],
      ["12/290006", "鳀鱼（非活）"],
      ["12/290153", "裹面糊的香肠"],
      ["12/290235", "沙嗲烤肉串"],
      ["12/300194", "味噌"],
      ["12/300254", "（加入饮料用的）冰块"],
      ["12/310162", "鳀鱼（活的）"],
      ["12/340046", "吸入型烟草用加热设备"],
      ["12/350099", "撰写广告文本"],
      ["12/350101", "广告版面设计"],
      ["12/350104", "广告片制作"],
      ["12/350113", "点击付费广告"],
      ["12/350121", "广告概念开发"],
      ["12/350187", "在虚拟环境中通过植入式广告为他人进行市场营销"],
      ["12/360108", "典当"],
      ["12/370162", "细木工服务（木制品修理）"],
      ["12/410208", "通过视频点播服务提供不可下载的电影"],
      ["12/420213", "活立木的质量评估"],
      ["12/440228", "葡萄栽培咨询"],
      ["12/440246", "作业疗法"],
      ["12/450243", "救生员服务"],
      ["12/450250", "入殓师服务"],
      ["12/C030041", "桉叶油"],
      ["12/C250034", "宗教服装"],
    ]);
    for (const [key, name] of pageChecked) {
      const [edition, code] = key.split("/");
      assert.equal(row(Number(edition), code)?.name, name, key);
    }
    // Checked on the page as not printed in this edition (ABSENT).
    for (const key of ["11/090748", "11/090749", "11/C240050"]) {
      const [edition, code] = key.split("/");
      assert.equal(row(Number(edition), code), undefined, key);
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

  it("SQL ships a balanced-alias view for merged synonyms", () => {
    const sql = readFileSync(
      join(import.meta.dirname, "../sql/postgresql/trademark_nice_snapshots.sql"),
      "utf-8",
    );
    assert.match(sql, /CREATE OR REPLACE VIEW "trademark_nice_snapshot_alias"/);
    assert.match(sql, /string_to_array\("name", '，'\)/);
    assert.match(
      sql,
      /AND length\(translate\("alias", '（\(', ''\)\) = length\(translate\("alias", '）\)', ''\)\)/,
    );
  });

  it("alias splitting resolves single-synonym lookups in every edition", () => {
    // 与 SQL 视图同逻辑：按全角逗号拆分 item 名称，只保留括号平衡的片段。
    const balanced = (a: string) =>
      (a.match(/[（(]/g) ?? []).length === (a.match(/[）)]/g) ?? []).length;
    const aliases = (name: string) =>
      name.split("，").map((p) => p.trim()).filter(balanced);
    const find = (edition: number, a: string) =>
      editions
        .get(edition)!
        .filter((r) => r.type === "item" && aliases(r.name).includes(a))
        .map((r) => r.code);
    assert.deepEqual(find(13, "计量仪表"), ["090138"]); // 「计数器，计量仪表」
    assert.deepEqual(find(13, "苏打灰"), ["010100"]); // 「纯碱，苏打灰」
    assert.deepEqual(find(10, "蓄电池用防泡沫溶液"), ["010006"]);
    for (const { edition } of snapshots)
      for (const row of editions.get(edition)!)
        if (row.type === "item")
          for (const a of aliases(row.name))
            assert.ok(a.length > 0, `empty alias at ${edition}/${row.code}`);
  });
});
