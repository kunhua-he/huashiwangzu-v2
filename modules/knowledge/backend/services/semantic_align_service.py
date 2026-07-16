"""语义打齐服务（文本层字级权威为锚，全自动、不硬编码、零LLM）。

核心尺子：逐字位滑窗。对一个实体名的每个汉字位置，用它左右窗口去"干净文本层"
(base_parse 非图片 chunk)查这一位到底该是啥字。文本层碾压者≠当前字 → OCR/VLM 错字，
就地修正；干净名每位都与文本层一致 → 不动（绝对安全）。单个名字即可自纠，不需兄弟变体。

护栏(三条,防误伤)：
  1) 只纠汉字(英文设计师码/标点/数字原样保留)
  2) 权威字也必须是汉字(不拿标点/字母替换汉字)
  3) 左右窗口都得非空(句首句尾单边空→证据太松,保守跳过)

依据：华哥"文本直接提取的词组,最多语序混乱,文字100%不会出错"。文本层=权威真值。
用途：graph 节点抽完实体后自动打齐(增量);批处理脚本清存量(同一函数)。owner_id 由调用方传。
"""
from __future__ import annotations

import logging
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.semantic_align")

# ── 尺子参数（数据驱动，非行业硬编码；可按语料调）──
WIN = 2            # 左右各取几个字当上下文窗口
AUTH_RATIO = 10    # 权威字块数 ≥ 次高 × 此倍数 = 碾压
AUTH_MIN = 5       # 权威字最少文本层块数（证据下限，防小样本抖动）
VALID_MIN = 3      # 当前字在该位文本层出现 ≥ 此数 = 真值(不是错字),不动
                   # 例:"广花X路"里"二"出现8次→广花二路是真路,不能并进广花一路
# 短上下文护栏:3字词(变化位左右各1字)模式太泛,很多合法字都能填(透X肌/超X水/养X粥),
# 弱权威会把合法词误改成另一合法词。所以短上下文必须权威极强(专名级)才动。
# 数据实测:好例娇薇诗2019/苏蜜雅956(短) vs 坏例透美肌157/圣痘士46(短) → 300 干净分开。
SHORT_CTX_MAX = 3      # 左右上下文合计 ≤ 此数 = 短上下文
SHORT_AUTH_MIN = 300   # 短上下文时权威字最少块数(专名级碾压)
SHORT_ATTEST_MIN = 50  # 短上下文时改后完整名最少命中文档数
SUBWORD_REAL_MIN = 5   # 短上下文:原词变化位两侧2字子串命中≥此数=真词,原词合法→不并(护栏7)
                       # 阈值5:救回"工位区"(工位7篇),误伤零容忍优先;漏合并(如护养品)=安全
_IMG_EXT = ("jpg", "png", "jpeg", "gif", "bmp", "webp", "tiff", "svg")
_IMG_EXT_SQL = "(" + ",".join(f"'{e}'" for e in _IMG_EXT) + ")"


def _is_cjk(ch: str) -> bool:
    """是否汉字。只对汉字做 OCR 纠错，其余原样保留。"""
    return bool(ch) and "一" <= ch <= "鿿"


def _cjk_run(chars: list[str], start: int, step: int, limit: int) -> str:
    """从 start 沿 step 方向收集最多 limit 个连续汉字,碰到非汉字即停。返回顺序还原的串。

    防止窗口吃进数字/门牌号(如"广花X路237"里的数字),那会把上下文锁死到唯一门牌,
    掩盖同位真值竞争(广花一路 vs 广花二路),导致真地址被误并。
    """
    out: list[str] = []
    i = start
    while 0 <= i < len(chars) and len(out) < limit and _is_cjk(chars[i]):
        out.append(chars[i])
        i += step
    if step < 0:
        out.reverse()
    return "".join(out)


async def _slot_authority(db: AsyncSession, owner_id: int, left: str, right: str) -> list[tuple[str, int]]:
    """查 'left + X + right' 中 X 在干净文本层（排图片）的字→文档数分布，降序。

    优先查预计算表 kb_char_slot_authority(O(1)索引命中,<1ms);表为空则退化回全表正则扫。
    预计算表根治了"20万次全表扫把DB当处理器"的CPU爆满问题。
    """
    if not left or not right:
        return []
    # 优先:查预计算表(btree索引,毫秒级)
    try:
        r = await db.execute(
            sa_text(
                """SELECT mid_char, cnt FROM kb_char_slot_authority
                   WHERE owner_id=:o AND left_ctx=:l AND right_ctx=:r
                   ORDER BY cnt DESC"""
            ),
            {"o": owner_id, "l": left, "r": right},
        )
        rows = [(ch, int(n)) for ch, n in r.all() if ch and ch.strip()]
        return rows  # 命中→已按cnt降序;未命中→空(保守不改,不再全表扫爆CPU)
    except Exception:
        # 仅预计算表异常时才退化全表扫(正常不会走到)
        pat = f"{_re_escape(left)}(.){_re_escape(right)}"
        rex = f"{_re_escape(left)}.{_re_escape(right)}"
        r = await db.execute(
            sa_text(
                f"""
                SELECT substring(c.text from :pat) AS ch, COUNT(*) AS n
                FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                WHERE c.owner_id = :o AND c.index_layer = 'base_parse'
                  AND d.extension NOT IN {_IMG_EXT_SQL}
                  AND c.text ~ (:re)
                GROUP BY substring(c.text from :pat)
                """
            ),
            {"pat": pat, "re": rex, "o": owner_id},
        )
        rows = [(ch, int(n)) for ch, n in r.all() if ch and ch.strip()]
        return sorted(rows, key=lambda x: -x[1])


def _re_escape(s: str) -> str:
    import re
    return re.escape(s)


# 语义终审:证据驱动裁定循环(取证工具组备证据→喂模型判)。零行业硬编码,换行业只换库。
# 黄金集实测:乱并=0,该并侧证据充分全对。候选极少(几万里十几个),不拖慢。


async def _semantic_gate(orig: str, fixed: str, evidence: int, db: AsyncSession = None, owner_id: int = 0) -> bool:
    """证据驱动裁定:orig 是 fixed 的OCR错写(该并)→True;orig 是合法独立词(不该并)→False。

    调裁定循环(取证工具组备齐证据→deepseek单轮判+置信度+留言)。
    高置信判并→True;低置信/证据不足→进留言表+返回False(保守不并)。
    无db时退化为旧逻辑(裸判,兼容旧调用方式)。异常→False(保守不并)。
    """
    if db is not None and owner_id:
        try:
            from .实体裁定循环 import 裁定
            return await 裁定(db, owner_id, orig, fixed)
        except Exception as exc:  # noqa: BLE001
            logger.warning("证据驱动裁定异常(保守不并) %s→%s: %s", orig, fixed, exc)
            return False
    # 无db退化:直接调网关裸判(旧逻辑,兼容)
    try:
        from app.gateway.router import gateway_router
        import re as _re, json as _json
        sys_p = (
            "你是中文实体校对专家,判断原词是不是候选词的OCR错写。"
            "差异字形近/音近→并;差异字是不同含义的正常字→留。拿不准判留。"
            "只输出JSON:{\"判定\":\"并\"或\"留\"}"
        )
        res = await gateway_router.chat(
            [{"role": "system", "content": sys_p},
             {"role": "user", "content": f"原词:{orig}\n候选词:{fixed}"}],
            profile_key="deepseek-v4-flash",
        )
        m = _re.search(r'\{.*\}', res.get("content", "") or "", _re.S)
        return _json.loads(m.group(0)).get("判定", "") == "并" if m else False
    except Exception as exc:  # noqa: BLE001
        logger.warning("语义终审失败(保守不并) %s→%s: %s", orig, fixed, exc)
        return False


async def _name_attested(db: AsyncSession, owner_id: int, name: str) -> int:
    """修正后的完整名，在干净文本层(base_parse 非图片)逐字命中多少篇文档。

    终极护栏:文本层=100%正确真值。改后的串若在文本层真实存在→是真规范名;
    查无此串→LLM/OCR臆造,驳回。这一条把"公司名纠错(华世王镞集团25篇)"与
    "把合法词改成另一合法词(肌肤生态臆造句0篇)"彻底分开。
    """
    r = await db.execute(
        sa_text(
            f"""SELECT count(DISTINCT c.document_id)
                FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                WHERE c.owner_id = :o AND c.index_layer = 'base_parse'
                  AND d.extension NOT IN {_IMG_EXT_SQL}
                  AND c.text LIKE :w"""
        ),
        {"o": owner_id, "w": f"%{name}%"},
    )
    return int(r.first()[0])


async def canonicalize_name(db: AsyncSession, owner_id: int, name: str, semantic_gate: bool = False) -> tuple[str, list[dict]]:
    """逐字位自纠一个实体名。返回 (规范名, 改动明细列表)。

    改动明细: [{"pos":i,"from":原字,"to":权威字,"evidence":权威块数,"runner_up":次高块数}]
    无改动 → 返回 (原名, [])。
    semantic_gate=True:频率护栏通过后,本地模型终审灰区(两个都像真词的,如皮脂vs硬脂),兜最后1%。
    """
    if not name or len(name) < 2:
        return name, []
    # 快速排除:VLM像素属性数据混入实体表的噪音(主色#xxx/边缘密度0.xx/平均亮度…)
    # 这些不是实体名,不可能有OCR错字需要纠,跳过零精度损失(抽样验证20/20全是纯像素数据)。
    import re as _re_mod
    if _re_mod.match(r'\s*(主色|边缘密度|平均亮度|占比|纹理|色温|饱和度|对比度|颜色分布|亮度)', name):
        return name, []
    # 便宜预筛:整名在干净文本层逐字命中(≥3字走trgm索引,快)=已是正确名,直接跳过逐字扫。
    # 第一性原理:整名在100%正确的文本层里真实存在→它就是对的,无需纠错。
    if len(name) >= 3 and await _name_attested(db, owner_id, name) >= 1:
        return name, []
    chars = list(name)
    fixes: list[dict] = []
    for i in range(len(chars)):
        if not _is_cjk(chars[i]):
            continue  # 护栏1
        # 窗口只取相邻汉字,碰到数字/标点/字母就停(否则'路2'把上下文锁死,掩盖竞争真值)
        left = _cjk_run(chars, i - 1, -1, WIN)
        right = _cjk_run(chars, i + 1, 1, WIN)
        if not left or not right:
            continue  # 护栏3
        ranked = await _slot_authority(db, owner_id, left, right)
        if not ranked:
            continue
        top_ch, top_n = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0
        if top_ch == chars[i]:
            continue  # 当前字就是权威 → 不动
        if not _is_cjk(top_ch):
            continue  # 护栏2
        cur_n = next((n for ch, n in ranked if ch == chars[i]), 0)
        if cur_n >= VALID_MIN:
            continue  # 护栏4:当前字在该位文本层真实出现≥VALID_MIN次→是真值,不是错字
        # 护栏6:短上下文(3字词,左右各1字)模式太泛,弱权威会把合法词误改成另一合法词。
        # 必须权威极强(专名级)才动。数据实测:娇薇诗2019/苏蜜雅956留,透美肌157/圣痘士46驳。
        short_ctx = (len(left) + len(right)) <= SHORT_CTX_MAX
        auth_floor = SHORT_AUTH_MIN if short_ctx else AUTH_MIN
        if top_n >= max(auth_floor, second * AUTH_RATIO):
            fixes.append({"pos": i, "from": chars[i], "to": top_ch, "evidence": top_n,
                          "runner_up": second, "short_ctx": short_ctx})
            chars[i] = top_ch  # 就地修正，后续窗口用修正后的字
    corrected = "".join(chars)
    if not fixes:
        return name, []
    # 终极护栏:改后完整名必须在干净文本层真实存在,否则驳回(防臆造/合法词误改)。
    # 短上下文再加码:改后名须命中≥SHORT_ATTEST_MIN篇(专名才有这么高覆盖)。
    attested = await _name_attested(db, owner_id, corrected)
    min_attest = SHORT_ATTEST_MIN if any(f.get("short_ctx") for f in fixes) else 1
    if attested < min_attest:
        return name, []
    # 护栏7(子串真词检查,纯规则):短上下文改动,若原词变化字两侧的2字子串在文本层是真词
    # (如"皮脂"80篇、"工位"、"四方"),说明原词是合法词非乱码→留(不并)。
    # 只有原词子串全查无(乱码,如"娇巢/巢诗"=0)才允许并。宁漏勿错(漏=安全)。
    for f in fixes:
        if not f.get("short_ctx"):
            continue
        i = f["pos"]
        for bigram in (name[max(0, i - 1):i + 1], name[i:i + 2]):
            if len(bigram) == 2 and _is_cjk(bigram[0]) and _is_cjk(bigram[1]):
                if await _name_attested(db, owner_id, bigram) >= SUBWORD_REAL_MIN:
                    return name, []  # 原词含真词子串→是合法词,不并
    # 护栏8(长上下文GPT终审):长上下文(≥4字名)纯规则挡不住"两个都真词"的词义差异
    # (皮肤无弹性vs的弹性、纯利润vs毛利润)。GPT当法官,只有判"并"才并。GPT死→不并(安全)。
    # 短上下文已被护栏6/7保住,不走GPT(省额度)。semantic_gate=False时长上下文一律不并(保守)。
    is_long = any(not f.get("short_ctx") for f in fixes)
    if is_long:
        if not semantic_gate:
            return name, []  # 未开GPT终审→长上下文一律保守不并
        if not await _semantic_gate(name, corrected, attested, db=db, owner_id=owner_id):
            return name, []  # 裁定"留"→不并
    return corrected, fixes


async def _resolve_canonical_entity(db: AsyncSession, owner_id: int, canonical_name: str, category: str) -> int:
    """锚点实体id：库里有同名(非merged)→用它;没有→新建。返回 entity_id。"""
    r = await db.execute(
        sa_text(
            """SELECT id FROM kb_entity_dictionary
               WHERE owner_id=:o AND name=:n AND status != 'merged'
               ORDER BY id LIMIT 1"""
        ),
        {"o": owner_id, "n": canonical_name},
    )
    row = r.first()
    if row:
        return int(row[0])
    ins = await db.execute(
        sa_text(
            """INSERT INTO kb_entity_dictionary(owner_id,name,category,status,source,created_at,updated_at)
               VALUES(:o,:n,:c,'confirmed','semantic_align',now(),now()) RETURNING id"""
        ),
        {"o": owner_id, "n": canonical_name, "c": category or "通用"},
    )
    return int(ins.first()[0])


async def _merge_variant_into(
    db: AsyncSession, owner_id: int, variant_id: int, variant_name: str,
    canonical_id: int, canonical_name: str, fixes: list[dict],
) -> None:
    """把变体实体并入锚点：证据链改指向、注册别名、标 merged、写日志。变体条目保留(可回溯)。"""
    if variant_id == canonical_id:
        return
    # 1) chunk_entities / evidence 改指向锚点(无唯一约束,直接UPDATE;后续dedup由检索DISTINCT兜底)
    await db.execute(
        sa_text("UPDATE kb_chunk_entities SET entity_id=:c WHERE entity_id=:v AND owner_id=:o"),
        {"c": canonical_id, "v": variant_id, "o": owner_id},
    )
    await db.execute(
        sa_text("UPDATE kb_evidence SET entity_id=:c WHERE entity_id=:v AND owner_id=:o"),
        {"c": canonical_id, "v": variant_id, "o": owner_id},
    )
    # 2) 图谱节点改指向锚点(label 也跟着规范名)
    await db.execute(
        sa_text("UPDATE kb_graph_nodes SET entity_id=:c, label=:n WHERE entity_id=:v AND owner_id=:o"),
        {"c": canonical_id, "n": canonical_name, "v": variant_id, "o": owner_id},
    )
    # 3) 变体名注册成锚点别名(搜变体也能命中锚点;去重)
    exists = await db.execute(
        sa_text("SELECT 1 FROM kb_entity_aliases WHERE owner_id=:o AND entity_id=:c AND alias=:a"),
        {"o": owner_id, "c": canonical_id, "a": variant_name},
    )
    if not exists.first():
        await db.execute(
            sa_text(
                """INSERT INTO kb_entity_aliases(owner_id,entity_id,alias,created_at,updated_at)
                   VALUES(:o,:c,:a,now(),now())"""
            ),
            {"o": owner_id, "c": canonical_id, "a": variant_name},
        )
    # 4) 变体字典条目标 merged + canonical_id + 落盘依据(可回溯)
    await db.execute(
        sa_text(
            """UPDATE kb_entity_dictionary
               SET status='merged', canonical_id=:c,
                   semantic_meta=CAST(:meta AS json),
                   updated_at=now()
               WHERE id=:v AND owner_id=:o"""
        ),
        {"c": canonical_id, "v": variant_id, "o": owner_id,
         "meta": _json({"打齐依据": "文本层字级权威", "改动": fixes, "规范名": canonical_name})},
    )
    # 5) 合并日志
    await db.execute(
        sa_text(
            """INSERT INTO kb_entity_merge_log(owner_id,source_entity_ids,target_entity_id,merged_by,reason,created_at,updated_at)
               VALUES(:o,CAST(:src AS json),:t,:o,:reason,now(),now())"""
        ),
        {"o": owner_id, "src": _json([variant_id]), "t": canonical_id,
         "reason": f"文本层打齐: {variant_name} → {canonical_name}"},
    )


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


async def align_document_entities(db: AsyncSession, document_id: int, owner_id: int) -> dict:
    """逐文档打齐入口(graph 节点抽完实体后调 / 批处理复用)。

    取本文档 chunk_entities 触达的所有实体名 → 逐个滑窗自纠 → 变了就并入锚点。
    幂等:已 merged 的跳过;规范名==原名的不动。返回统计。
    """
    stats = {"checked": 0, "aligned": 0, "details": []}
    r = await db.execute(
        sa_text(
            """SELECT DISTINCT ed.id, ed.name, ed.category
               FROM kb_chunk_entities ce
               JOIN kb_entity_dictionary ed ON ed.id=ce.entity_id AND ed.owner_id=ce.owner_id
               WHERE ce.document_id=:d AND ce.owner_id=:o AND ed.status != 'merged'"""
        ),
        {"d": document_id, "o": owner_id},
    )
    entities = [(int(eid), name, cat) for eid, name, cat in r.all()]
    for eid, name, category in entities:
        stats["checked"] += 1
        canonical_name, fixes = await canonicalize_name(db, owner_id, name)
        if not fixes or canonical_name == name:
            continue
        canonical_id = await _resolve_canonical_entity(db, owner_id, canonical_name, category)
        await _merge_variant_into(db, owner_id, eid, name, canonical_id, canonical_name, fixes)
        stats["aligned"] += 1
        stats["details"].append({"from": name, "to": canonical_name, "fixes": fixes})
    if stats["aligned"]:
        await db.commit()
        logger.info("文档 %d 语义打齐: 检查 %d 实体, 修正 %d 个", document_id, stats["checked"], stats["aligned"])
    return stats
