# -*- coding: utf-8 -*-
"""实体裁定循环(护栏8的"小agent",零行业硬编码)。

给(原词,候选词),流程:取证工具组备齐证据 → 喂模型判 → 输出 判定+置信度+留言。
- 高置信 → 直接返回裁定(并/留),调用方据此执行合并
- 低置信/证据不足(如两边都0篇,没权威铁证) → 写进裁定留言表待人复核,返回"待定"(=不并,安全)

规范可配置(存 kb_verdict_rule 或此处常量),换行业调规范不改逻辑。判据数据驱动,不写死行业词。
第一性原理(华哥):文本层100%正确。候选词高频=对;原词查无=变体。拿不准就留言,别瞎判。
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from .实体裁定取证工具组 import 查词频, 查上下文, 差异字定位, _IMG_EXT_SQL

logger = logging.getLogger(__name__)

# 置信门槛:模型置信度低于此→不直接执行,进留言表待复核(华哥"拿不准建表存,等我决策")
置信门槛 = 0.75

_判据 = (
    "你是中文实体校对专家。判断【原词】是不是【候选词】的错别字误写(该并),还是独立正常词(该留)。\n"
    "系统已备好证据,不用你猜:\n"
    "- 候选词在本库干净原文出现篇数(高=库里权威真实写法)\n"
    "- 原词篇数(0=库里没这词,大概率变体误写)\n"
    "- 差异字(第几字不同,原字→候选字)\n"
    "- 候选词真实上下文片段\n\n"
    "判【并】:候选词高频、原词篇数≈0、差异字形近/音近误认(族↔镞、菁↔精、巢↔薇)→原词是错写。\n"
    "判【留】:满足任一即留——\n"
    "  · 原词库里也有篇数(真实独立词)\n"
    "  · 差异字是常用功能词(的/性/无/不/或/和/为/型/者)\n"
    "  · 差异字致词义不同(利润vs毛利、师vs院、展示vs显示、录播vs直播、券vs场)\n"
    "  · 【重要】两个替换字如果各自都能和前后字组成有独立含义的常见词——留!\n"
    "    例:展示屏/显示屏(展示和显示都是正常词)=留; 型皮肤/性皮肤(敏感型和敏感性都成词)=留;\n"
    "    停车券/停车场(券和场各组词)=留。这些不是OCR错认,是两个不同的正常词。\n"
    "    只有差异字在视觉上很像(笔画相似/形近)或读音接近(音近)才叫OCR误认。\n"
    "证据不足(两词篇数都0,没权威铁证)→置信度给低分(≤0.5),让人复核。\n"
    "拿不准一律判【留】。只输出JSON: {\"判定\":\"并\"或\"留\",\"置信度\":0到1的小数,\"因\":\"简短\"}"
)


async def 备证据(db: AsyncSession, owner_id: int, 原词: str, 候选词: str, 上下文条数: int = 3) -> dict:
    """调取证工具组,一次备齐裁定所需的全部证据。上下文条数可按轮次递增。"""
    return {
        "原词": 原词,
        "候选词": 候选词,
        "候选词篇数": await 查词频(db, owner_id, 候选词),
        "原词篇数": await 查词频(db, owner_id, 原词),
        "差异字": [f"第{d['位']}字 {d['原字']}→{d['候选字']}" for d in 差异字定位(原词, 候选词)],
        "候选词上下文": await 查上下文(db, owner_id, 候选词, 条数=上下文条数),
        "原词上下文": await 查上下文(db, owner_id, 原词, 条数=上下文条数),
    }


async def _模型裁定(证据: dict, profile_key: str) -> tuple[str, float, str]:
    """喂证据给模型,返回 (判定, 置信度, 留言)。异常→('留',0.0,原因),保守不并。"""
    from app.gateway.router import gateway_router

    usr = "证据:\n" + json.dumps(证据, ensure_ascii=False) + "\n\n原词是候选词的错写吗?"
    try:
        res = await gateway_router.chat(
            [{"role": "system", "content": _判据}, {"role": "user", "content": usr}],
            profile_key=profile_key,
        )
        m = re.search(r"\{.*\}", res.get("content", "") or "", re.S)
        if not m:
            return "留", 0.0, "模型无有效JSON输出"
        d = json.loads(m.group(0))
        判定 = d.get("判定", "留")
        置信 = float(d.get("置信度", 0.0) or 0.0)
        因 = str(d.get("因", ""))[:200]
        return (判定 if 判定 in ("并", "留") else "留"), 置信, 因
    except Exception as exc:  # noqa: BLE001
        logger.warning("实体裁定模型调用失败(保守不并) %s→%s: %s", 证据.get("原词"), 证据.get("候选词"), exc)
        return "留", 0.0, f"模型异常:{str(exc)[:80]}"


async def _落留言(db: AsyncSession, owner_id: int, 原词: str, 候选词: str,
                 判定: str, 置信: float, 留言: str, 证据: dict, profile_key: str,
                 entity_id: int | None) -> None:
    """低置信/证据不足→写留言表待人复核,绝不写死DB(华哥铁律)。"""
    await db.execute(
        sa_text("""
            INSERT INTO kb_entity_verdict_review
              (owner_id, entity_id, orig_name, cand_name, verdict, confidence,
               agent_note, evidence_json, judged_by, review_status)
            VALUES (:o, :eid, :orig, :cand, :v, :c, :note,
                    CAST(:ev AS JSONB), :by, 'pending')
            ON CONFLICT (owner_id, orig_name, cand_name) DO NOTHING
        """),
        {"o": owner_id, "eid": entity_id, "orig": 原词, "cand": 候选词,
         "v": 判定, "c": 置信, "note": 留言,
         "ev": json.dumps(证据, ensure_ascii=False), "by": profile_key},
    )
    await db.commit()


async def _查来源文件(db: AsyncSession, owner_id: int, 词: str) -> list[str]:
    """查该词出现在哪些文件里(给人工审核定位用)。"""
    r = await db.execute(
        sa_text(
            f"""SELECT DISTINCT d.original_filename
                FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                WHERE c.owner_id = :o AND c.index_layer = 'base_parse'
                  AND d.extension NOT IN {_IMG_EXT_SQL}
                  AND c.text LIKE :w
                LIMIT 10"""
        ),
        {"o": owner_id, "w": f"%{词}%"},
    )
    return [f for (f,) in r.all() if f]


async def 裁定(db: AsyncSession, owner_id: int, 原词: str, 候选词: str,
              profile_key: str = "deepseek-v4-flash",
              entity_id: int | None = None,
              最大轮数: int = 5) -> bool:
    """护栏8入口(多轮取证版):返回 True=该并,False=不并。

    流程:
    1. 第1轮:备3条上下文 → 模型判
    2. 置信<门槛 → 补充更多上下文(条数翻倍)再判,最多5轮
    3. 5轮仍不够 → 留言表(含来源文件列表供人工定位)+返回False(保守不并)
    4. 任何轮高置信判并 → True;判留 → False
    """
    上下文条数 = 3
    最终证据 = None
    for 轮 in range(1, 最大轮数 + 1):
        证据 = await 备证据(db, owner_id, 原词, 候选词, 上下文条数=上下文条数)
        最终证据 = 证据
        判定, 置信, 留言 = await _模型裁定(证据, profile_key)

        # 高置信判并 → 直接执行
        if 判定 == "并" and 置信 >= 置信门槛:
            return True
        # 判留(不管置信高低) → 不并,安全
        if 判定 == "留":
            return False
        # 判并但低置信 → 证据可能不够,下一轮补更多上下文
        if 轮 < 最大轮数:
            上下文条数 = min(上下文条数 * 2, 20)  # 翻倍但不超20条
            continue
        # 最后一轮仍低置信 → 进留言表,带来源文件信息供人工审核
        来源文件 = await _查来源文件(db, owner_id, 候选词)
        原词来源 = await _查来源文件(db, owner_id, 原词)
        审核备注 = (
            f"经{最大轮数}轮取证仍无法高置信判定(最终置信{置信})。\n"
            f"理由:{留言}\n"
            f"候选词'{候选词}'出现在:{来源文件[:5]}\n"
            f"原词'{原词}'出现在:{原词来源[:5]}\n"
            f"请人工对照原始文件判断是否为OCR错字。"
        )
        try:
            await _落留言(db, owner_id, 原词, 候选词, "待定", 置信,
                        审核备注, 最终证据, profile_key, entity_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("裁定留言落库失败(非致命): %s", exc)
        return False
    return False
