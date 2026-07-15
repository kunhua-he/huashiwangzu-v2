# -*- coding: utf-8 -*-
"""批_图片重融去噪 的主逻辑续(被主文件 import)。拆分只为控制单文件行数。"""
import asyncio, json, time
from sqlalchemy import text as T
from app.database import AsyncSessionLocal
from app.gateway.router import gateway_router


async def refuse_one(sys_p, doc_id, page, ocr, vision, tech_attr, mod, dry):
    """重融一页:云端优先(未死且未超预算),否则本地。写回 kb_page_fusions。返回('cloud'/'local'/'fail')。"""
    user_msg = mod._img_user_msg(ocr, vision)
    parsed = None
    used = "fail"
    # 降级链(华哥定):GPT(responses,本地路由) → deepseek(网关云端) → 本地gemma。
    # 层1:GPT。未标死才试。503/额度类累计到阈值→标死跳过。
    if not mod._state.get("gpt_dead"):
        mod._state["cloud_calls"] += 1
        try:
            parsed = await mod._gpt_fuse(sys_p, user_msg)
            if parsed:
                used = "gpt"
        except Exception as exc:
            err = str(exc)
            if any(k in err for k in ("401", "402", "403", "429", "503")):
                mod._state["gpt_503"] = mod._state.get("gpt_503", 0) + 1
                if mod._state["gpt_503"] >= 20:  # 连续额度类错误达阈值→GPT永久标死,不再浪费
                    mod._state["gpt_dead"] = True
                    print(f"  !GPT额度耗尽(503累计{mod._state['gpt_503']}),永久降级 deepseek/本地", flush=True)
    # 层2:deepseek 云端(网关)。gpt失败或已死时试。deepseek也标死则跳过。
    if parsed is None and not mod._state.get("ds_dead"):
        try:
            res = await gateway_router.chat(
                [{"role": "system", "content": sys_p}, {"role": "user", "content": user_msg}],
                profile_key=mod.CLOUD_PROFILE,
            )
            if res.get("error"):
                err = str(res.get("error"))
                if any(k in err.lower() for k in ("quota", "402", "403", "429", "insufficient", "exhaust", "balance")):
                    mod._state["ds_dead"] = True
                    print(f"  !deepseek额度耗尽,永久降级本地: {err[:60]}", flush=True)
            else:
                parsed = mod._parse(res.get("content", ""))
                if parsed:
                    used = "deepseek"
        except Exception:
            pass
    # 层3:本地 gemma 兜底
    if parsed is None:
        try:
            parsed = await mod._local_fuse(sys_p, user_msg)
            if parsed:
                used = "local"
        except Exception as exc:
            print(f"  !本地也失败 doc{doc_id}p{page}: {str(exc)[:80]}", flush=True)
            return "fail"
    if not parsed or not (parsed.get("fused_text") or "").strip():
        return "fail"
    if dry:
        return used
    # 写回:fused_text去噪 + 技术属性归位
    attrs = dict(parsed.get("attributes") or {})
    if tech_attr:
        attrs["图像技术属性"] = tech_attr
    async with AsyncSessionLocal() as db:
        await db.execute(T("""
            UPDATE kb_page_fusions SET
              fused_text=:ft, page_summary=:ps, page_title=:pt,
              body_json=CAST(:bj AS json), attributes_json=CAST(:aj AS json), tags_json=CAST(:tg AS json),
              fusion_status='done', updated_at=now()
            WHERE document_id=:d AND page=:p AND owner_id=:o
        """), {
            "ft": parsed.get("fused_text", "")[:8000], "ps": parsed.get("page_summary", ""),
            "pt": parsed.get("page_title"), "bj": json.dumps(parsed.get("entities") or [], ensure_ascii=False),
            "aj": json.dumps(attrs, ensure_ascii=False), "tg": json.dumps(parsed.get("tags") or [], ensure_ascii=False),
            "d": doc_id, "p": page, "o": 4,
        })
        await db.commit()
    return used
