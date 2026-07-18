# -*- coding: utf-8 -*-
"""字级权威滑窗：复用 canonicalize_name 的滑窗思路，尺子=同页文本层。

干什么：
- 从尺子文本构建 (左窗口, 右窗口) → 中间字 权威表
- 对脏文本(OCR/VLM)逐汉字位查权威，当前字不是权威且自己在尺子该位查无 → 纠正

入参/出参：
- 构建字位权威(尺子文本) → 权威表
- 滑窗纠正(脏文本, 权威表, 尺子文本) → (纠正后文本, 改动明细列表)

与 semantic_align_service.canonicalize_name 的差异：
- 尺子从「全库 base_parse」换成「同文档同页 text content」
- 权威计数以本页为准，阈值放宽(单页样本少)
- 对 OCR 常见的「字间空格」做汉字流压缩后再滑窗，再映射回原文位置

依赖：无外部服务，纯规则。
"""
from __future__ import annotations

from collections import Counter, defaultdict

# 与 semantic_align_service 对齐的窗口
窗口 = 2
# 权威门槛(2026-07-18 华哥体检收紧)：
# 旧值=1 → 误纠率 51.89%,病根是"文本层出现1次就当铁证"。收到 2:
# 只有尺子在同一(左,右)窗口出现≥2次的字才够格当权威,砍掉 63% 的 evidence=1 瞎改。
权威最少 = 2
当前真值最少 = 1
# 否定词:改错会直接翻转语义(不→等 把否定抹掉),代价最高。要更硬的证据(≥3)才敢动。
否定词集 = {"不", "无", "未", "非", "没", "莫", "勿", "别"}
否定词权威最少 = 3
# 品牌字黑名单:高频品牌串"华世王镞"里的"镞/臻"会污染尺子,把普通连词误纠成品牌字
# (及→镞)。to 落在黑名单时,左窗口必须真是品牌窗口才允许,否则驳回。
品牌污染字 = {"镞", "臻"}
品牌左窗白名单 = {"王", "世王", "华世王", "世", "华"}


def 是否汉字(ch: str) -> bool:
    """是否汉字。只对汉字做纠错，其余原样保留。"""
    return bool(ch) and "一" <= ch <= "鿿"


def 取连续汉字(chars: list[str], start: int, step: int, limit: int) -> str:
    """从 start 沿 step 方向收集最多 limit 个连续汉字。复用 _cjk_run 语义。"""
    out: list[str] = []
    i = start
    while 0 <= i < len(chars) and len(out) < limit and 是否汉字(chars[i]):
        out.append(chars[i])
        i += step
    if step < 0:
        out.reverse()
    return "".join(out)


def 压缩汉字流(文本: str) -> tuple[list[str], list[int]]:
    """抽出汉字流及其在原文中的下标，供滑窗后映射回写。"""
    字: list[str] = []
    位: list[int] = []
    for i, ch in enumerate(文本 or ""):
        if 是否汉字(ch):
            字.append(ch)
            位.append(i)
    return 字, 位


def 构建字位权威(尺子文本: str, 窗: int = 窗口) -> dict[tuple[str, str], Counter]:
    """从尺子文本(压缩汉字流)构建 (左,右) → 中间字计数。"""
    字, _ = 压缩汉字流(尺子文本)
    表: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for i in range(len(字)):
        left = 取连续汉字(字, i - 1, -1, 窗)
        right = 取连续汉字(字, i + 1, 1, 窗)
        if not left or not right:
            continue
        表[(left, right)][字[i]] += 1
    return 表


def 串在尺子中(串: str, 尺子文本: str) -> bool:
    """改后片段必须真实存在于尺子(压缩后也算命中)。"""
    if not 串:
        return False
    if 串 in (尺子文本 or ""):
        return True
    尺字, _ = 压缩汉字流(尺子文本)
    尺串 = "".join(尺字)
    return 串 in 尺串


def 滑窗纠正(
    脏文本: str,
    权威表: dict[tuple[str, str], Counter],
    尺子文本: str,
    *,
    路名: str = "",
) -> tuple[str, list[dict]]:
    """对脏文本做字级权威滑窗纠正。

    返回 (纠正后原文, 改动明细)。
    改动明细: [{pos, from, to, left, right, evidence, 路}]
    无改动 → (原文, [])。
    """
    if not 脏文本 or not 权威表 or not 尺子文本:
        return 脏文本 or "", []

    字, 原位 = 压缩汉字流(脏文本)
    if len(字) < 2:
        return 脏文本, []

    改动: list[dict] = []
    for i in range(len(字)):
        left = 取连续汉字(字, i - 1, -1, 窗口)
        right = 取连续汉字(字, i + 1, 1, 窗口)
        if not left or not right:
            continue
        分布 = 权威表.get((left, right))
        if not 分布:
            continue
        排序 = 分布.most_common()
        权威字, 权威数 = 排序[0]
        次高 = 排序[1][1] if len(排序) > 1 else 0
        当前 = 字[i]
        if 权威字 == 当前:
            continue
        if not 是否汉字(权威字):
            continue
        当前数 = 分布.get(当前, 0)
        # 当前字在该位尺子里真实出现过 → 真值，不动
        if 当前数 >= 当前真值最少:
            continue
        # 护栏(收紧):否定词改错=翻转语义,代价最高,要 evidence≥否定词权威最少 才敢动
        门槛 = 否定词权威最少 if 当前 in 否定词集 else 权威最少
        if 权威数 < 门槛:
            continue
        if 次高 > 0 and 权威数 <= 次高:
            continue
        # 护栏(收紧):品牌污染字(镞/臻)只有左窗口真是品牌窗口才允许,否则驳回(防 及→镞)
        if 权威字 in 品牌污染字 and left not in 品牌左窗白名单:
            continue
        # 护栏(收紧):空上下文防御(理论上 106 行已挡,双保险防漂移产出空窗改动)
        if not left or not right:
            continue
        # 终极护栏：left+权威字+right 必须在尺子里真实存在
        候选片段 = left + 权威字 + right
        if not 串在尺子中(候选片段, 尺子文本):
            continue
        # 原片段 left+当前+right 若也在尺子里 → 两个都真，灰区，本函数不改(留给裁定)
        原片段 = left + 当前 + right
        if 串在尺子中(原片段, 尺子文本):
            continue

        改动.append(
            {
                "pos": 原位[i],
                "from": 当前,
                "to": 权威字,
                "left": left,
                "right": right,
                "evidence": 权威数,
                "runner_up": 次高,
                "路": 路名,
            }
        )
        字[i] = 权威字  # 就地修正，后续窗口用修正后的字

    if not 改动:
        return 脏文本, []

    # 映射回原文：只替换改动位的汉字
    原文列表 = list(脏文本)
    for f in 改动:
        p = f["pos"]
        if 0 <= p < len(原文列表) and 原文列表[p] == f["from"]:
            原文列表[p] = f["to"]
        else:
            # 位漂移保护：在邻近找原字
            for j in range(max(0, p - 3), min(len(原文列表), p + 4)):
                if 原文列表[j] == f["from"] and 是否汉字(原文列表[j]):
                    原文列表[j] = f["to"]
                    f["pos"] = j
                    break
    return "".join(原文列表), 改动


def 双路互校纠正(
    甲文本: str,
    乙文本: str,
    *,
    甲路名: str = "ocr",
    乙路名: str = "vision",
) -> tuple[str, str, list[dict], list[dict]]:
    """无文本层时：两路互为弱尺子。

    规则(保守)：
    - 用乙构建权威表纠甲；用甲构建权威表纠乙
    - 只有权威位唯一且对方流里真实存在 left+权威+right 才改
    - 若出现对倒改(甲 A→B 且乙 B→A 同窗口) → 两边都丢弃(进灰区，宁漏勿错)
    - 分歧且两边都有支持 → 不改，由调用方进留言

    返回 (纠后甲, 纠后乙, 甲改动, 乙改动)
    """
    甲权威 = 构建字位权威(乙文本)
    乙权威 = 构建字位权威(甲文本)
    纠甲, 甲改 = 滑窗纠正(甲文本, 甲权威, 乙文本, 路名=甲路名)
    纠乙, 乙改 = 滑窗纠正(乙文本, 乙权威, 甲文本, 路名=乙路名)

    # 剔除对倒改：同 left/right 窗口下 甲 from→to 与 乙 to→from
    def _窗键(f: dict) -> tuple[str, str, str, str]:
        return (f.get("left") or "", f.get("right") or "", f.get("from") or "", f.get("to") or "")

    甲键集 = {_窗键(f) for f in 甲改}
    丢甲: set[int] = set()
    丢乙: set[int] = set()
    for j, f in enumerate(乙改):
        反 = (f.get("left") or "", f.get("right") or "", f.get("to") or "", f.get("from") or "")
        if 反 in 甲键集:
            丢乙.add(j)
            for i, g in enumerate(甲改):
                if _窗键(g) == 反:
                    丢甲.add(i)
    if 丢甲 or 丢乙:
        甲改 = [f for i, f in enumerate(甲改) if i not in 丢甲]
        乙改 = [f for j, f in enumerate(乙改) if j not in 丢乙]
        # 按保留改动重放写回(从原文重新应用)
        纠甲 = _应用改动(甲文本, 甲改)
        纠乙 = _应用改动(乙文本, 乙改)
    return 纠甲, 纠乙, 甲改, 乙改


def _应用改动(原文: str, 改动: list[dict]) -> str:
    """把改动列表应用到原文(按 pos 替换 from→to)。"""
    if not 改动:
        return 原文
    chars = list(原文 or "")
    for f in 改动:
        p = f.get("pos")
        fr = f.get("from")
        to = f.get("to")
        if p is None or fr is None or to is None:
            continue
        if 0 <= int(p) < len(chars) and chars[int(p)] == fr:
            chars[int(p)] = to
    return "".join(chars)


def 收集灰区候选(
    脏文本: str,
    权威表: dict[tuple[str, str], Counter],
    尺子文本: str,
    *,
    路名: str = "",
    上限: int = 20,
) -> list[dict]:
    """捞「两个都像真词」的灰区：当前字与权威字都能在尺子成词，交裁定循环。"""
    if not 脏文本 or not 权威表:
        return []
    字, 原位 = 压缩汉字流(脏文本)
    候选: list[dict] = []
    for i in range(len(字)):
        if len(候选) >= 上限:
            break
        left = 取连续汉字(字, i - 1, -1, 窗口)
        right = 取连续汉字(字, i + 1, 1, 窗口)
        if not left or not right:
            continue
        分布 = 权威表.get((left, right))
        if not 分布:
            continue
        排序 = 分布.most_common()
        权威字, 权威数 = 排序[0]
        当前 = 字[i]
        if 权威字 == 当前 or not 是否汉字(权威字):
            continue
        当前数 = 分布.get(当前, 0)
        if 当前数 < 1:
            continue
        原词 = left + 当前 + right
        候选词 = left + 权威字 + right
        if not (串在尺子中(原词, 尺子文本) and 串在尺子中(候选词, 尺子文本)):
            continue
        候选.append(
            {
                "pos": 原位[i],
                "原词": 原词,
                "候选词": 候选词,
                "from": 当前,
                "to": 权威字,
                "evidence": 权威数,
                "路": 路名,
            }
        )
    return 候选
