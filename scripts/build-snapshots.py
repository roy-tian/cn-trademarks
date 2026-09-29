"""Assemble the NCL11–13 snapshots from mainland (CNIPA) sources only.

Usage: python scripts/build-snapshots.py <2022-draft.jsonl> <2025-draft.jsonl>
       <output-dir> [--review <review.jsonl>]
Run from the repository root after extract-scanned.py (the two OCR drafts)
and extract-revision.py (scripts/ncl13-2026-revision.tsv).

Sources, all CN:
- the 2022 and 2025 OCR drafts: every printed listing (code, name, group, page);
- data/snapshots/ncl10-2016.jsonl: the 2016 text layer;
- data/nice.jsonl: an independent visual extraction of the 2025 text with the
  2026 revision applied;
- scripts/ncl13-2026-revision.tsv: the 2026 revision list.

RapidOCR drops or confuses rare characters (鞣, 朊, element names), so no OCR
text is trusted on its own.  A name is kept only when another CN source
agrees with it after normalising punctuation, and the agreeing source's text
is used.  When the OCR is garbled, a text that two independent CN sources
agree on is used instead.  Anything else must be checked on the page image
and recorded in NAMES, VERIFIED or TITLES; --review writes the open cases to
a file instead of failing.

NCL13 is NCL12 with the 2026 revision applied per listing: one code can be
printed in several groups, and the revision adds, deletes and renames each
printing separately.  An item's parentCode is its first group in book order
(the lowest group code); its synonyms are joined with "，" in book order.
"""

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import NoReturn

args = sys.argv[1:]
review_path = None
if "--review" in args:
    i = args.index("--review")
    if i + 1 >= len(args):
        raise SystemExit("--review needs a file")
    review_path = Path(args[i + 1])
    del args[i : i + 2]
if len(args) != 3:
    raise SystemExit(
        "usage: build-snapshots.py <2022-draft> <2025-draft> <output-dir> [--review <file>]"
    )
draft_files = {2022: args[0], 2025: args[1]}
output_dir = Path(args[2])


def rows(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


# The 2016 text layer uses half-width punctuation; the 2022+ texts are
# typeset with full-width punctuation throughout.
FULLWIDTH = str.maketrans({"(": "（", ")": "）", ",": "，", ";": "；", ":": "："})


def fullwidth(s):
    return s.translate(FULLWIDTH)


def synonyms(name):
    """Split a merged name on "，", keeping commas inside brackets."""
    parts, current = [], ""
    for piece in name.split("，"):
        current = f"{current}，{piece}" if current else piece
        if len(re.findall(r"[（(]", current)) == len(re.findall(r"[）)]", current)):
            parts.append(current)
            current = ""
    return parts + ([current] if current else [])


def similarity(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---------------------------------------------------------------- sources --
ncl10 = {r["code"]: r for r in rows("data/snapshots/ncl10-2016.jsonl")}
legacy = {r["code"]: r for r in rows("data/nice.jsonl")}
revision = [
    dict(zip(("group", "op", "code", "name", "new"), line.split("\t")))
    for line in Path("scripts/ncl13-2026-revision.tsv")
    .read_text(encoding="utf-8")
    .splitlines()[1:]
]
drafts = {year: rows(path) for year, path in draft_files.items()}

# Names the revision quotes as they were printed in the 2025 text.
revision_2025 = defaultdict(list)
for op in revision:
    if op["op"] in ("delete", "rename", "renumber"):
        revision_2025[op["code"]].append(op["name"])
# Names that only exist from 2026 on, so they are no evidence for 2025: new
# names, and added names of a code the revision quotes under another 2025
# name (120340 轴承（车辆部件） -> 轴承（运载工具部件）).  An addition without
# such a quote may be a move out of a deleted group (0305 化妆用杏仁油).
revision_2026 = defaultdict(set)
for op in revision:
    if op["op"] == "rename":
        revision_2026[op["code"]].add(norm(op["new"]))
    if op["op"] == "add" and op["code"] in revision_2025:
        if norm(op["name"]) not in {norm(n) for n in revision_2025[op["code"]]}:
            revision_2026[op["code"]].add(norm(op["name"]))

# The revision gives items moved in from class 03/11 C codes that the 2025
# text still prints for other items, without deleting those items.  A code
# keeps one meaning per edition, so NCL13 follows the revision and drops the
# 2025 item (the same reading as the 0.1.x releases).
REASSIGNED_2026 = {
    "C010254": "固化剂",
    "C010255": "纤维素浆",
    "C250033": "雨披",
    "C250034": "宗教服装",
}


# Names checked on the page images where no second source settles the OCR:
# (year, code) -> names; each unsettled printing takes the most similar one.
NAMES = {
    (2022, "010728"): ["制食品用植物提取物", "食品工业用植物提取物"],
    (2022, "020005"): ["食用色素", "食品用着色剂"],
    (2022, "020113"): ["羰基（木头防腐剂）"],
    (2022, "020134"): ["木地板面漆"],
    (2022, "040065"): ["工业用菜油", "工业用菜籽油"],
    (2022, "060047"): ["金属装甲板"],
    (2022, "060208"): ["金属制帐篷地钉"],
    (2022, "090113"): ["非人工呼吸用呼吸面罩"],
    (2022, "090755"): ["安全令牌（加密装置）"],
    (2022, "090757"): ["掌上电脑用套"],
    (2022, "090778"): ["科学研究用具有人工智能的人形机器人"],
    (2022, "090780"): ["电子香烟用电池"],
    (2022, "090804"): ["移动电话用可下载图像"],
    (2022, "090881"): ["移动电话和智能手机专用支架"],
    (2022, "090885"): ["色盲矫正眼镜"],
    (2022, "090896"): ["移动电话和智能手机专用仪表板防滑垫"],
    (2022, "100160"): ["医用气雾剂分配器"],
    (2022, "100276"): ["吸入器用分隔器"],
    (2022, "100304"): ["超声波面部美容治疗仪"],
    (2022, "110352"): ["家用电动米糕机"],
    (2022, "110359"): ["医学贮存用冰箱、冷却装置和冰柜"],
    (2022, "110370"): ["烟雾机"],
    (2022, "110380"): ["水过滤装置用过滤器", "水过滤设备用膜"],
    (2022, "120129"): ["铁路冷藏货车"],
    (2022, "120154"): ["挡风玻璃", "风挡"],
    (2022, "120249"): ["野营车", "房车"],
    (2022, "120279"): ["无人驾驶汽车", "自动驾驶汽车"],
    (2022, "120306"): ["救援用雪橇"],
    (2022, "120326"): ["两栖车"],
    (2022, "120331"): ["运输用船型雪橇"],
    (2022, "140182"): ["帽子用装饰针"],
    (2022, "140183"): ["贵金属制雕塑纪念杯"],
    (2022, "160224"): ["纸张压摺器（办公用品）"],
    (2022, "180144"): ["手提箱用分装收纳袋", "行李箱用成套收纳袋"],
    (2022, "200045"): ["仿制玳瑁"],
    (2022, "200084"): ["非金属制固定式毛巾分配器"],
    (2022, "200143"): ["运输物品用带盖篮"],
    (2022, "200360"): ["服装用塑料或橡胶制缝制标签"],
    (2022, "210379"): ["制刷用猪鬃"],
    (2022, "210385"): ["厨房用研钵"],
    (2022, "210396"): ["烹饪网袋（非微波炉用）"],
    (2022, "210430"): ["售时为空的化妆用印章"],
    (2022, "210432"): ["自动开闭的垃圾桶"],
    (2022, "210433"): ["声波震动发梳"],
    (2022, "210437"): ["分菜匙"],
    (2022, "220045"): ["软百叶帘用梯形带"],
    (2022, "220068"): ["运输和贮存散装物用麻袋"],
    (2022, "250179"): ["柔道服"],
    (2022, "260143"): ["帽子用非装饰别针"],
    (2022, "280030"): ["草地滚球比赛用球"],
    (2022, "290048"): ["食品用果冻"],
    (2022, "290068"): ["肉汁"],
    (2022, "290072"): ["奶饮料（以奶为主）"],
    (2022, "290176"): ["低脂土豆片", "低脂炸土豆片"],
    (2022, "300293"): ["裹巧克力的炸土豆片"],
    (2022, "320008"): ["制作无酒精饮料用配料"],
    (2022, "320009"): ["制作饮料用无酒精原汁"],
    (2022, "320013"): ["制作加气水用配料", "制作碳酸水用配料"],
    (2022, "320017"): ["气泡水"],
    (2022, "320063"): ["制作饮料用淀粉基干混料"],
    (2022, "340040"): ["电子香烟烟液"],
    (2022, "350172"): ["组织商业活动"],
    (2022, "370156"): ["非研究目的的废址挖掘"],
    (2022, "370157"): ["通过远程监控系统对电梯（升降机）进行保养"],
    (2022, "390076"): ["提供关于贮藏服务的信息"],
    (2022, "390094"): ["电子数据或文件载体的物理贮存"],
    (2022, "390126"): ["为运输目的对人员和货物进行定位和追踪"],
    (2022, "400133"): ["定制生产小船", "定制生产游艇"],
    (2022, "400136"): ["航空器的定制装配", "定制生产航空器"],
    (2022, "410064"): ["提供关于消遣活动的信息"],
    (2022, "410220"): ["柔道训练"],
    (2022, "410239"): ["提供培训和教育考试（教育认证服务）"],
    (2022, "410242"): ["组织娱乐活动"],
    (2022, "420193"): ["测量"],
    (2022, "440166"): ["树木修剪"],
    (2022, "440250"): ["为残疾人提供服务性动物"],
    (2022, "450232"): ["遛狗服务"],
    (2022, "450257"): ["定位和追踪失踪人员和财产"],
    (2025, "010404"): ["预防小麦枯萎病的化学制剂", "预防小麦黑穗病的化学制剂"],
    (2025, "010710"): ["厩肥"],
    (2025, "020113"): ["木头防腐用羰基化合物"],
    (2025, "030099"): ["醚类香精"],
    (2025, "030110"): ["香叶醇"],
    (2025, "030159"): ["萜烯烃（香精油）"],
    (2025, "030226"): ["香橼香精油"],
    (2025, "030270"): ["芳香疗法用香精油"],
    (2025, "030274"): ["芳香疗法用香精油制乳霜"],
    (2025, "050222"): ["治小麦枯萎病的化学制剂", "治小麦黑穗病的化学制剂"],
    (2025, "060232"): ["（储液或储气用）金属容器"],
    (2025, "060260"): ["金属制楣窗"],
    (2025, "070610"): ["味噌制造机"],
    # The print gives 电动榨果汁机 the code "0705650" just before this item.
    (2025, "070611"): ["制备饮料用机械臂"],
    (2025, "070622"): ["舷外马达"],
    (2025, "080172"): ["撞锤（手工具）", "撞杵（手工具）"],
    (2025, "080236"): ["剁肉刀"],
    (2025, "090876"): ["伺服电机用电子控制器"],
    (2025, "090885"): ["色觉缺陷矫正眼镜"],
    (2025, "090886"): ["具有超声波清洗功能的隐形眼镜盒"],
    (2025, "100182"): ["医用吸入剂给药装置"],
    (2025, "100257"): ["氢吸入器"],
    (2025, "100290"): ["植入式避孕器"],
    (2025, "100305"): ["震颤患者用勺"],
    (2025, "120296"): ["铰接式公共汽车用铰接箱"],
    (2025, "120306"): ["救援用雪橇"],
    (2025, "120331"): ["运输用船型雪橇"],
    (2025, "160224"): ["纸张压摺器（办公用品）"],
    (2025, "170131"): ["O形密封圈"],
    (2025, "190179"): ["非金属制楣窗"],
    (2025, "190269"): ["玩耍用沙"],
    (2025, "200045"): ["仿制玳瑁"],
    (2025, "200084"): ["非金属制毛巾分配器"],
    (2025, "210103"): ["烹饪用模具"],
    (2025, "210379"): ["制刷用猪鬃"],
    (2025, "210384"): ["厨房用杵"],
    (2025, "210442"): ["纸巾盒套"],
    (2025, "210470"): ["浴室用长柄水瓢"],
    (2025, "220114"): ["猪鬃*"],
    (2025, "250148"): ["班丹纳方绸（围巾）"],
    (2025, "290006"): ["鳀鱼（非活）"],
    (2025, "290153"): ["裹面糊的香肠"],
    (2025, "290235"): ["沙嗲烤肉串"],
    (2025, "300194"): ["味噌"],
    (2025, "300254"): ["（加入饮料用的）冰块"],
    (2025, "310162"): ["鳀鱼（活的）"],
    (2025, "340046"): ["吸入型烟草用加热设备"],
    (2025, "350121"): ["广告概念开发"],
    (2025, "350187"): ["在虚拟环境中通过植入式广告为他人进行市场营销"],
    (2025, "370162"): ["细木工服务（木制品修理）"],
    (2025, "410208"): ["通过视频点播服务提供不可下载的电影"],
    (2025, "420213"): ["活立木的质量评估"],
    (2025, "440228"): ["葡萄栽培咨询"],
    (2025, "440246"): ["作业疗法"],
    (2025, "450243"): ["救生员服务"],
    (2025, "450250"): ["入殓师服务"],
    (2025, "C030041"): ["桉叶油"],
    (2025, "C250034"): ["宗教服装"],
}
# Checked on the page images where the sources above do not settle an item:
# (year, code) -> every printing [(group, name)] in book order.  Also covers
# codes the OCR missed and printings the OCR put under the wrong group.
VERIFIED = {
    # 2022 page 38: a line of 0602 no OCR pass could read.
    (2022, "060011"): [("0602", "钢管")],
    (2022, "060014"): [("0602", "金属喷头")],
    (2022, "060021"): [("0602", "金属喷嘴")],
    (2022, "060058"): [("0602", "绳索用金属套管")],
    # 2022 printings that moved or were dropped by 2025.
    (2022, "210424"): [("2102", "售时为空的智能药瓶")],
    (2022, "250178"): [("2503", "空手道服")],
    (2022, "390123"): [("3905", "停车场服务")],
    (2022, "410246"): [("4102", "举办娱乐活动")],
    (2022, "420268"): [("4220", "用于制图或热成像的无人机测量服务")],
    (2022, "C090143"): [("0908", "行车记录仪")],
    # The 2025 print numbers 纸制或塑料制食品袋 (1609) 160410, the code it
    # also prints for 聚会用纸制装饰品 (1605); WIPO numbers the former 160409.
    (2025, "160409"): [("1609", "纸制或塑料制食品袋")],
    (2025, "160410"): [("1605", "聚会用纸制装饰品")],
    # One line of 3501 (page 230) that no OCR pass detected.
    (2025, "350099"): [("3501", "撰写广告文本")],
    (2025, "350101"): [("3501", "广告版面设计")],
    (2025, "350104"): [("3501", "广告片制作")],
    (2025, "350113"): [("3501", "点击付费广告")],
    # Printed under the 3609 heading, which the OCR could not read.
    (2025, "360031"): [("3609", "典当经纪")],
    (2025, "360108"): [("3609", "典当")],
}
# OCR artefacts that are not items (misread codes, note text): (year, code).
SPURIOUS = {(2022, "890090")}  # the 0602 line below, read as garbage
# Codes printed in the editions before and after but not in this one, checked
# on the page: 2022 lists 智能眼镜/智能手表 only as C090139/C090140 (0901 jumps
# from 090747 to 090751) and 皮褥子 as C180003.
ABSENT = {(2022, "090748"), (2022, "090749"), (2022, "C240050")}
# Class and group titles checked on the page: (year, code) -> title.
TITLES = {
    (2022, "01"): "用于工业、科学、摄影、农业、园艺和林业的化学品；未加工人造合成树脂，未加工塑料物质；灭火和防火用合成物；淬火和焊接用制剂；鞣制动物皮毛用物质；工业用黏合剂；油灰及其他膏状填料；堆肥，肥料，化肥；工业和科学用生物制剂。",
    (2022, "03"): "不含药物的化妆品和梳洗用制剂；不含药物的牙膏；香料，香精油；洗衣用漂白剂及其他物料；清洁、擦亮、去渍及研磨用制剂。",
    (2022, "11"): "照明、加热、冷却、蒸汽发生、烹饪、干燥、通风、供水以及卫生用装置和设备。",
    (2022, "1207"): "畜力车辆，雪橇",
    (2022, "1402"): "贵金属盒",
    (2022, "22"): "绳索和细绳；网；帐篷和防水遮布；纺织品或合成材料制遮篷；帆；运输和贮存散装物用麻袋；衬垫和填充材料（纸或纸板、橡胶、塑料制除外）；纺织用纤维原料及其替代品。",
    (2022, "32"): "啤酒；无酒精饮料；矿泉水和汽水；水果饮料及果汁；糖浆及其他用于制作无酒精饮料的制剂。",
    (2022, "34"): "烟草和烟草代用品；香烟和雪茄；电子香烟和吸烟者用口腔雾化器；烟具；火柴。",
    (2022, "3407"): "电子香烟及其部件",
    (2022, "36"): "金融，货币和银行服务；保险服务；不动产事务。",
    (2022, "45"): "法律服务；为有形财产和个人提供实体保护的安全服务；由他人提供的为满足个人需要的私人和社会服务。",
    (2025, "01"): "用于工业、科学、摄影、农业、园艺和林业的化学品；未加工人造合成树脂，未加工塑料物质；灭火和防火用合成物；淬火和焊接用制剂；鞣制动物皮毛用物质；工业用黏合剂；油灰及其他膏状填料；堆肥，肥料，化肥；工业和科学用生物制剂。",
    (2025, "03"): "不含药物的化妆品和梳洗用制剂；不含药物的牙膏；香料，香精油；洗衣用漂白剂及其他物料；清洁、擦亮及研磨用制剂。",
    (2025, "05"): "药品，医用和兽医用制剂；医用卫生制剂；医用或兽医用营养食物和物质，婴儿食品；人用和动物用膳食补充剂；膏药，绷敷材料；填塞牙孔用料，牙科用蜡；消毒剂；消灭有害动物制剂；杀真菌剂，除莠剂。",
    (2025, "08"): "手工具和器具（手动的）；刀、叉和匙餐具；除火器外的随身武器；剃刀。",
    (2025, "09"): "科学、研究、导航、测量、摄影、电影、视听、光学、衡具、量具、信号、侦测、测试、检验、救生和教学用装置及仪器；处理、开关、转换、积累、调节或控制电的配送或使用的装置和仪器；录制、传送、重放或处理声音、影像或数据的装置和仪器；已录制和可下载的媒体，计算机软件，录制和存储用空白的数字或模拟介质；投币启动设备用机械装置；收银机，计算设备；计算机和计算机外围设备；潜水服，潜水面罩，潜水用耳塞，潜水和游泳用鼻夹，潜水员手套，潜水呼吸器；灭火设备。",
    (2025, "10"): "外科、医疗、牙科和兽医用仪器及器械；假肢，假眼和假牙；矫形用物品；缝合材料；残疾人专用治疗装置；按摩器械；婴儿护理用器械、器具及用品；性生活用器械、器具及用品。",
    (2025, "26"): "花边，编带和刺绣品，缝纫用饰带和蝴蝶结；纽扣，领钩扣，饰针和缝针；人造花；发饰；假发。",
    (2025, "1207"): "畜力车辆，雪橇",
    (2025, "3609"): "典当",
    (2025, "29"): "肉，鱼，家禽和野味；肉汁；腌渍、冷冻、干制及煮熟的水果和蔬菜；果冻，果酱，蜜饯；蛋；奶，奶酪，黄油，酸奶和其他奶制品；食用油和油脂。",
}


# ------------------------------------------------------------- resolution --
open_cases = []


def item_sources(year, code, built):
    """Candidate texts per independent CN source for one code and edition."""
    sources = {}
    if year == 2025:
        sources["revision"] = revision_2025.get(code, [])
        if code in legacy and code not in REASSIGNED_2026:
            sources["legacy"] = [
                s
                for s in synonyms(legacy[code]["name"])
                if norm(s) not in revision_2026.get(code, ())
            ]
    else:
        if code in built:
            sources["ncl12"] = [name for _, name in built[code]]
        # A 2026 name can be the 2022 one again (010729 drops 除香精油外).
        if code in legacy:
            sources["legacy"] = synonyms(legacy[code]["name"])
    if code in ncl10:
        sources["ncl10"] = [fullwidth(s) for s in synonyms(ncl10[code]["name"])]
    return sources


# (code, normalised 2025 OCR string) -> verified NCL12 names.  Two OCR runs
# over two printings that read the same string saw the same text, so a 2022
# printing that OCRs identically to a 2025 one has that verified name, as long
# as the string stands for one name only.
same_as_2025 = defaultdict(set)


def resolve(year, code, text, sources, other_ocr, taken=frozenset()):
    """Return the verified text for one OCR string, or None.

    In order: an exact match with a CN source; a name checked on the page
    (NAMES); a text two independent CN sources agree on when the OCR is
    garbled.  taken: names another printing of the code in the same group
    already matched exactly; a group does not print one name twice.
    """
    n = norm(text)
    if year == 2022 and n and len(same_as_2025.get((code, n), ())) == 1:
        return next(iter(same_as_2025[(code, n)]))
    for texts in sources.values():
        for candidate in texts:
            if n and norm(candidate) == n:
                return candidate
    if (year, code) in NAMES:
        names = [c for c in NAMES[(year, code)] if norm(c) not in taken]
        return max(names or NAMES[(year, code)], key=lambda c: similarity(text, c))
    # Garbled OCR: accept a text two independent sources agree on.
    support = defaultdict(set)
    for source, texts in sources.items():
        for candidate in texts:
            support[norm(candidate)].add(source)
    for candidate in other_ocr:
        support[norm(candidate)].add("other-ocr")
    agreed = []
    for texts in sources.values():
        for candidate in texts:
            key = norm(candidate)
            if year == 2025:
                # The revision quotes the 2025 print, and the legacy file is a
                # second reading of it; 2016 or 2022 alone may predate a change.
                # A revision quote alone is not enough: it can differ from the
                # print (170092).
                trusted = bool(support[key] & {"revision", "legacy"}) and len(support[key]) >= 2
            else:
                # NCL12, the legacy file and the 2025 OCR all read the 2025
                # text; only an agreeing 2016 text brackets 2022.
                trusted = "ncl10" in support[key] and len(support[key]) >= 2
            if trusted and candidate not in agreed:
                agreed.append(candidate)
    # Only the synonym this printing resembles most may be taken: an item's
    # other synonyms are agreed on as well (010404 枯萎病 vs 黑穗病).
    candidates = [c for texts in sources.values() for c in texts if norm(c) not in taken]
    if candidates:
        best = max(candidates, key=lambda c: similarity(text, c))
        single = len({norm(c) for c in candidates}) == 1  # 锕 read as 铜: nothing to confuse
        if best in agreed and (single or similarity(text, best) >= 0.5):
            return best
    return None


def with_star(name, text):
    """The * cross-group marker as this edition prints it: taken from the
    OCR (it agrees with the legacy extraction on all 2025 printings), since a
    reference text from another edition can differ (010007 醋酸盐（化学品）*)."""
    if not norm(text):
        return name
    return name.rstrip("*") + ("*" if text.rstrip().endswith("*") else "")


def open_case(year, kind, code, why, **details):
    open_cases.append({"year": year, "kind": kind, "code": code, "why": why, **details})


def build_edition(year, expected, known, parents, built_2025=None):
    """Resolve one OCR draft into listings: code -> [(group, name)].

    expected: codes other CN sources say are printed in this edition;
    known: codes a CN source confirms may be printed; parents: code -> groups
    a CN source puts the code in (one of them must be among its printings).
    """
    draft = {r["code"]: r for r in drafts[year] if r["type"] == "item"}
    other = drafts[2022 if year == 2025 else 2025]
    other_names = {
        r["code"]: [name for _, name, _ in r["listings"]]
        for r in other
        if r["type"] == "item"
    }
    listings = {}
    for code, r in draft.items():
        # A code is only printed within its own class; anything else is a
        # code read out of a garbled line (110090 in 0602 on 2022 p.38).
        r["listings"] = [p for p in r["listings"] if p[0][:2] == code.lstrip("C")[:2]]
        if (year, code) in SPURIOUS or not r["listings"]:
            continue  # a VERIFIED entry for the code is added below
        if (year, code) in VERIFIED:
            listings[code] = list(VERIFIED[(year, code)])
            if year == 2025 and len(listings[code]) == len(r["listings"]):
                for (_, text, _), (_, name) in zip(r["listings"], listings[code]):
                    same_as_2025[(code, norm(text))].add(name)
            continue
        sources = item_sources(year, code, built_2025 or {})
        page = r["page"]
        if code not in known:
            open_case(year, "item", code, "no CN source has this code", ocr=r["listings"], page=page)
        groups = {g for g, _, _ in r["listings"]}
        if parents.get(code) and not groups & parents[code]:
            open_case(year, "item", code, f"printed in {sorted(groups)}, sources say {sorted(parents[code])}",
                      ocr=r["listings"], page=page)
        resolved = []
        exact = {
            (g, norm(c))
            for g, text, _ in r["listings"]
            for texts in sources.values()
            for c in texts
            if norm(text) and norm(c) == norm(text)
        }
        for group, text, page in r["listings"]:
            taken = frozenset(n for g, n in exact if g == group and n != norm(text))
            name = resolve(year, code, text, sources, other_names.get(code, []), taken)
            if name is None:
                open_case(year, "item", code, "name", ocr=text, group=group, page=page, sources=sources)
                name = text
            name = with_star(name, text)
            if year == 2025 and norm(text):
                same_as_2025[(code, norm(text))].add(name)
            resolved.append((group, name))
        if len(set(resolved)) < len({(g, norm(t)) for g, t, _ in r["listings"]}):
            # Two differently read printings in one group took the same name:
            # a synonym would silently disappear when names are merged.
            open_case(year, "item", code, "printings resolved to one name", ocr=r["listings"],
                      resolved=resolved, page=r["page"])
        listings[code] = resolved
    for (y, code), printed in VERIFIED.items():
        if y == year and code not in listings:
            listings[code] = list(printed)
    for code in sorted(expected - set(listings) - {c for y, c in ABSENT if y == year}):
        open_case(year, "item", code, "missing from the OCR", sources=item_sources(year, code, built_2025 or {}))
    return listings


def build_titles(year, kind, reference):
    """Resolve class or group titles against CN reference titles."""
    titles = {}
    for r in drafts[year]:
        if r["type"] != kind:
            continue
        code = r["code"]
        if (year, code) in TITLES:
            titles[code] = TITLES[(year, code)]
            continue
        candidates = [t for t in reference(code) if t]
        match = next((t for t in candidates if norm(t) == norm(r["name"])), None)
        agreed = [t for t in candidates if sum(norm(u) == norm(t) for u in candidates) >= 2]
        if match is None and agreed and similarity(r["name"], agreed[0]) >= 0.5:
            match = agreed[0]  # both references agree; the OCR is garbled
        if match is None:
            open_case(year, kind, code, "title", ocr=r["name"], page=r["page"], sources=candidates)
            match = r["name"]
        titles[code] = match
    # Headings the OCR could not read at all ("3609 典当" came out "原单609").
    width = 2 if kind == "class" else 4
    for (y, code), title in TITLES.items():
        if y == year and len(code) == width and code not in titles:
            titles[code] = title
    return dict(sorted(titles.items()))


def reference_titles(*editions):
    def lookup(code):
        return [
            fullwidth(e[code]["name"]) if e is ncl10 else e[code]["name"]
            for e in editions
            if code in e
        ]

    return lookup


def snapshot_rows(year, classes, groups, listings, versions=None):
    result = []
    for code, name in classes.items():
        result.append({"code": code, "name": name, "type": "class", "parentCode": None})
    for code, name in groups.items():
        result.append({"code": code, "name": name, "type": "group", "parentCode": code[:2]})
    for code, printed in listings.items():
        ordered = sorted(printed, key=lambda listing: listing[0])  # stable: book order
        names = []
        for _, name in ordered:
            if name not in names:
                names.append(name)
        result.append(
            {
                "code": code,
                "name": "，".join(names),
                "type": "item",
                "parentCode": ordered[0][0],
            }
        )
    for r in result:
        r["version"] = (versions or {}).get(r["code"], str(year))
    return result


def save(path, arr):
    arr.sort(key=lambda r: r["code"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in arr:
            ordered = {k: r[k] for k in ("code", "name", "type", "parentCode", "version")}
            f.write(json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n")


# ------------------------------------------------------------------ NCL12 --
deleted_groups = {op["group"] for op in revision if op["op"] == "group-delete"}
# Codes the 2026 revision creates; every other legacy code was printed in 2025.
# An added code the revision quotes (a 2025 printing) or an international code
# 2016 prints (moved out of a deleted group: 030100) is not new, and must be in
# the OCR.  C codes can be reused (C250035 头巾 in 2016, 电热靴 in 2026).
created_2026 = {op["new"] for op in revision if op["op"] == "renumber"} | (
    {op["code"] for op in revision if op["op"] == "add"}
    - set(revision_2025)
    - {c for c in ncl10 if not c.startswith("C")}
)
legacy_items = {c for c, r in legacy.items() if r["type"] == "item"}
expected_2025 = (legacy_items - created_2026) | set(revision_2025) | set(REASSIGNED_2026)
known_2025 = expected_2025 | {
    r["code"]
    for r in drafts[2025]
    if r["type"] == "item" and any(g in deleted_groups for g, _, _ in r["listings"])
}
parents_2025 = {
    c: {legacy[c]["parentCode"]} for c in legacy_items - created_2026 if legacy[c]["version"] == "2025"
}
listings_2025 = build_edition(2025, expected_2025, known_2025, parents_2025)
classes_2025 = build_titles(2025, "class", reference_titles(legacy, ncl10))
groups_2025 = build_titles(2025, "group", reference_titles(legacy, ncl10))

# ------------------------------------------------------------------ NCL11 --
built_2025 = listings_2025
ncl10_items = {c for c, r in ncl10.items() if r["type"] == "item"}
parents_2022 = {c: {g for g, _ in built_2025[c]} for c in built_2025}
for c in ncl10_items:
    parents_2022.setdefault(c, set()).add(ncl10[c]["parentCode"])
listings_2022 = build_edition(
    2022, ncl10_items & set(built_2025), ncl10_items | set(built_2025), parents_2022, built_2025
)
classes_2022 = build_titles(
    2022, "class", reference_titles({c: {"name": n} for c, n in classes_2025.items()}, ncl10)
)
groups_2022 = build_titles(
    2022, "group", reference_titles({c: {"name": n} for c, n in groups_2025.items()}, ncl10)
)

# ------------------------------------------------------------------ NCL13 --
listings_2026 = {code: list(printed) for code, printed in listings_2025.items()}
groups_2026 = dict(groups_2025)
changed = set()


def fail(op, why) -> NoReturn:
    raise SystemExit(f"revision {op['group']} {op['op']} {op['code']} {op['name']}: {why}")


def find_listing(printed, group, name, op):
    """Indexes of the printings an operation targets.

    The revision's quotes of 2025 names can differ slightly from the 2025
    print (170092 is quoted "非文具用、…" but printed "非文具、…"); a lone
    printing of the code in that group is accepted when it is close enough.
    """
    hits = [i for i, (g, n) in enumerate(printed) if g == group and norm(n) == norm(name)]
    if hits:
        return hits
    same = [i for i, (g, _) in enumerate(printed) if g == group]
    if len(same) == 1 and similarity(printed[same[0]][1], name) >= 0.75:
        print(f"2026: {op['code']} quoted {name!r}, 2025 prints {printed[same[0]][1]!r}", file=sys.stderr)
        return same
    fail(op, f"no such listing in {printed}")


phases = ["group-delete", "delete", "renumber", "rename", "add", "group-rename", "group-new"]
for op in revision:
    if op["op"] not in phases:
        fail(op, "unknown operation")
new_groups = {op["group"] for op in revision if op["op"] == "group-new"}
for phase in phases:
    for op in (o for o in revision if o["op"] == phase):
        group, code = op["group"], op["code"]
        if phase == "group-delete":
            if group not in groups_2026:
                fail(op, "group missing")
            del groups_2026[group]
            for c, printed in listings_2026.items():
                if any(g == group for g, _ in printed):
                    listings_2026[c] = [(g, n) for g, n in printed if g != group]
                    changed.add(c)
        elif phase == "delete":
            printed = listings_2026.get(code, [])
            hits = find_listing(printed, group, op["name"], op)
            listings_2026[code] = [p for i, p in enumerate(printed) if i not in hits]
            changed.add(code)
        elif phase == "renumber":
            # Only the named printing moves: 090381 避雷器 becomes 090955,
            # 090381 避雷针 keeps its code.
            printed = listings_2026.get(code, [])
            hits = find_listing(printed, group, op["name"], op)
            if op["new"] in listings_2026:
                fail(op, "new code already used")
            listings_2026[op["new"]] = [printed[i] for i in hits]
            listings_2026[code] = [p for i, p in enumerate(printed) if i not in hits]
            changed.update((code, op["new"]))
        elif phase == "rename":
            printed = listings_2026.get(code, [])
            for i in find_listing(printed, group, op["name"], op):
                printed[i] = (group, op["new"])
            changed.add(code)
        elif phase == "add":
            if group not in groups_2026 and group not in new_groups:
                fail(op, "group missing")
            printed = listings_2026.setdefault(code, [])
            if code in REASSIGNED_2026 and printed:
                if [n for _, n in printed] != [REASSIGNED_2026[code]]:
                    fail(op, f"expected to replace {REASSIGNED_2026[code]}, found {printed}")
                printed.clear()
            if any(g == group and norm(n) == norm(op["name"]) for g, n in printed):
                fail(op, "already listed")
            others = {norm(n) for _, n in printed}
            if others and norm(op["name"]) not in others:
                # A code keeps one meaning; only synonyms added in the same
                # group (100330 眼镜框/眼镜架) may differ.
                if not all(g == group for g, _ in printed):
                    fail(op, f"code already means {printed}")
            printed.append((group, op["name"]))
            changed.add(code)
        elif phase in ("group-rename", "group-new"):
            if (phase == "group-rename") != (group in groups_2026):
                fail(op, "group state")
            groups_2026[group] = op["new"]
            changed.add(group)
listings_2026 = {code: printed for code, printed in listings_2026.items() if printed}
# Retired groups stay printed without items ("0117 能源 注：本类似群第九版时移入
# 0407类似群"); any other group must keep at least one item.
used_2025 = {g for printed in listings_2025.values() for g, _ in printed}
used_2026 = {g for printed in listings_2026.values() for g, _ in printed}
for code in groups_2026:
    if code in used_2025 and code not in used_2026:
        raise SystemExit(f"2026: group {code} lost all its items")

# The revision abbreviates class-title edits ("修改为“……工业用黏合剂；堆肥……”"),
# so NCL13 takes the full 2026 titles from data/nice.jsonl.  Each must equal
# the NCL12 title or contain every quoted fragment of its revision entry.
TITLE_EDITS_2026 = {
    "01": ["工业用黏合剂；堆肥"],
    "03": ["不含药物的牙膏；香水；洗衣用漂白剂及其他物料"],
    "05": ["人和动物用膳食补充剂；橡皮膏；绷敷材料"],
    "08": ["手动的手工具和器具；"],
    "09": ["数据的装置和仪器；已录制和可下载的多媒体文件，计算机软件", "潜水用耳塞，潜水用鼻夹，潜水员手套"],
    "10": ["假牙；眼镜，隐形眼镜和太阳镜；矫形用物品；"],
    "26": ["花边和刺绣品，"],
    "29": ["和野味；烹饪用肉汁；腌渍、冷冻、干制及煮熟的水果、蔬菜和海藻；果冻"],
}
classes_2026 = {}
for code, title in classes_2025.items():
    new = legacy[code]["name"]
    fragments = TITLE_EDITS_2026.get(code)
    if fragments is None and new != title:
        open_case(2026, "class", code, "title differs from NCL12", ocr=title, sources=[new])
    if fragments and not all(f in new for f in fragments):
        open_case(2026, "class", code, f"title lacks {fragments}", sources=[new])
    classes_2026[code] = new
    if fragments:
        changed.add(code)

# ----------------------------------------------------------------- output --
if open_cases:
    if review_path is None:
        for case in open_cases[:40]:
            print(json.dumps(case, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(f"{len(open_cases)} names need review (see --review)")
    with review_path.open("w", encoding="utf-8") as f:
        for case in open_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(f"{len(open_cases)} open review cases -> {review_path}", file=sys.stderr)

versions_2026 = {code: "2026" if code in changed else "2025" for code in
                 list(classes_2026) + list(groups_2026) + list(listings_2026)}
for year, edition, classes, groups, listings, versions in [
    (2022, 11, classes_2022, groups_2022, listings_2022, None),
    (2025, 12, classes_2025, groups_2025, listings_2025, None),
    (2026, 13, classes_2026, groups_2026, listings_2026, versions_2026),
]:
    result = snapshot_rows(year, classes, groups, listings, versions)
    save(output_dir / f"ncl{edition}-{year}.jsonl", result)
    counts = {t: sum(r["type"] == t for r in result) for t in ("class", "group", "item")}
    print(year, counts, "total", len(result))
