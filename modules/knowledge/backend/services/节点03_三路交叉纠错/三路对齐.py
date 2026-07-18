# -*- coding: utf-8 -*-
"""三路对齐：文本层(尺)↔OCR↔VLM，产出每路应纠正的结果。

干什么：
- 按分支判定结果，对一页三路 content 做字级对齐纠错
- 三路互校：尺子=text，纠 ocr/vision
- OCR↔VLM 互校：两路互为弱尺子

入参：页数据 dict{text,ocr,vision,text_id,ocr_id,vision_id,page,...}
出参：{
  分支, 纠正项:[{raw_id, 路, 原content, 新content, 改动}],
  灰区:[{原词,候选词,路,pos,...}],
  跳过原因
}

依赖：分支判定、字级权威滑窗。不写库。
"""
from __future__ import annotations

from .分支判定 import 判定分支, 是否可用文本层, 是否有实质内容
from .字级权威滑窗 import (
    双路互校纠正,
    收集灰区候选,
    构建字位权威,
    滑窗纠正,
)


def 对齐一页(页数据: dict) -> dict:
    """对单页做三路对齐，不写库。"""
    分支 = 判定分支(页数据)
    结果: dict = {
        "page": 页数据.get("page"),
        "分支": 分支,
        "纠正项": [],
        "灰区": [],
        "跳过原因": None,
    }
    if 分支 == "跳过":
        结果["跳过原因"] = "无可纠内容"
        return 结果

    if 分支 == "三路互校":
        return _三路互校(页数据, 结果)
    return _双路互校(页数据, 结果)


def _meta已纠过(meta) -> bool:
    if meta is None:
        return False
    if isinstance(meta, dict):
        return isinstance(meta.get("纠错留痕"), (dict, list))
    if isinstance(meta, str):
        return '"纠错留痕"' in meta or "'纠错留痕'" in meta
    return False


def _三路互校(页数据: dict, 结果: dict) -> dict:
    尺子 = 页数据.get("text") or ""
    权威表 = 构建字位权威(尺子)

    for 路, 键, id键, meta键 in (
        ("ocr", "ocr", "ocr_id", "ocr_meta"),
        ("vision", "vision", "vision_id", "vision_meta"),
    ):
        脏 = 页数据.get(键) or ""
        raw_id = 页数据.get(id键)
        if not 是否有实质内容(脏) or not raw_id:
            continue
        # 幂等：该行已纠过 → 不再二次滑窗
        if _meta已纠过(页数据.get(meta键)):
            continue
        # vision 常带「素材类型/描述」包装，仍可纠其中可见汉字
        新文, 改动 = 滑窗纠正(脏, 权威表, 尺子, 路名=路)
        if 改动 and 新文 != 脏:
            结果["纠正项"].append(
                {
                    "raw_id": int(raw_id),
                    "路": 路,
                    "round": 2 if 路 == "ocr" else 3,
                    "原content": 脏,
                    "新content": 新文,
                    "改动": 改动,
                }
            )
        # 灰区：两个都真词，留给裁定(默认不自动改)
        灰 = 收集灰区候选(脏, 权威表, 尺子, 路名=路)
        for g in 灰:
            g["raw_id"] = int(raw_id)
            g["page"] = 页数据.get("page")
            结果["灰区"].append(g)

    return 结果


def _双路互校(页数据: dict, 结果: dict) -> dict:
    ocr = 页数据.get("ocr") or ""
    vision = 页数据.get("vision") or ""
    ocr_id = 页数据.get("ocr_id")
    vision_id = 页数据.get("vision_id")
    ocr已纠 = _meta已纠过(页数据.get("ocr_meta"))
    vision已纠 = _meta已纠过(页数据.get("vision_meta"))

    if ocr已纠 and vision已纠:
        结果["跳过原因"] = "本页已纠过"
        return 结果

    if not (是否有实质内容(ocr) or 是否有实质内容(vision)):
        结果["跳过原因"] = "OCR/VLM 皆空"
        return 结果

    纠ocr, 纠vision, 甲改, 乙改 = 双路互校纠正(ocr, vision)

    if (not ocr已纠) and 甲改 and ocr_id and 纠ocr != ocr:
        结果["纠正项"].append(
            {
                "raw_id": int(ocr_id),
                "路": "ocr",
                "round": 2,
                "原content": ocr,
                "新content": 纠ocr,
                "改动": 甲改,
            }
        )
    if (not vision已纠) and 乙改 and vision_id and 纠vision != vision:
        结果["纠正项"].append(
            {
                "raw_id": int(vision_id),
                "路": "vision",
                "round": 3,
                "原content": vision,
                "新content": 纠vision,
                "改动": 乙改,
            }
        )

    # 双路分歧灰区：OCR 与 VLM 压缩汉字流中同位不同且各自成词，进留言
    if 是否有实质内容(ocr) and 是否有实质内容(vision):
        from .字级权威滑窗 import 压缩汉字流, 取连续汉字, 是否汉字

        甲字, 甲位 = 压缩汉字流(ocr)
        乙字, _ = 压缩汉字流(vision)
        # 仅在较短流长度内粗对齐（无文本层时无严格对齐算法，保守取公共前缀窗口）
        n = min(len(甲字), len(乙字), 200)
        for i in range(n):
            if 甲字[i] == 乙字[i] or not 是否汉字(甲字[i]) or not 是否汉字(乙字[i]):
                continue
            left = 取连续汉字(甲字, i - 1, -1, 2)
            right = 取连续汉字(甲字, i + 1, 1, 2)
            if not left or not right:
                continue
            原词 = left + 甲字[i] + right
            候选词 = left + 乙字[i] + right
            结果["灰区"].append(
                {
                    "pos": 甲位[i] if i < len(甲位) else i,
                    "原词": 原词,
                    "候选词": 候选词,
                    "from": 甲字[i],
                    "to": 乙字[i],
                    "路": "ocr_vs_vision",
                    "raw_id": int(ocr_id) if ocr_id else None,
                    "page": 页数据.get("page"),
                }
            )
            if len(结果["灰区"]) >= 15:
                break

    return 结果


def 组页字典(行列表: list[dict]) -> dict[int, dict]:
    """把 kb_raw_data 行列表按 page 聚成 {page: {text,ocr,vision,ids...}}。"""
    页表: dict[int, dict] = {}
    for 行 in 行列表:
        page = int(行["page"])
        槽 = 页表.setdefault(
            page,
            {
                "page": page,
                "text": "",
                "ocr": "",
                "vision": "",
                "text_id": None,
                "ocr_id": None,
                "vision_id": None,
                "text_meta": None,
                "ocr_meta": None,
                "vision_meta": None,
            },
        )
        st = (行.get("source_type") or "").lower()
        rnd = int(行.get("round") or 0)
        content = 行.get("content") or ""
        rid = int(行["id"])
        meta = 行.get("metadata_json")
        if rnd == 1 or st == "text":
            # 多条 text 取最长可用
            if 是否可用文本层(content) and len(content) >= len(槽["text"] or ""):
                槽["text"] = content
                槽["text_id"] = rid
                槽["text_meta"] = meta
            elif not 槽["text"]:
                槽["text"] = content
                槽["text_id"] = rid
                槽["text_meta"] = meta
        elif rnd == 2 or st == "ocr":
            槽["ocr"] = content
            槽["ocr_id"] = rid
            槽["ocr_meta"] = meta
        elif rnd == 3 or st == "vision":
            槽["vision"] = content
            槽["vision_id"] = rid
            槽["vision_meta"] = meta
    return 页表
