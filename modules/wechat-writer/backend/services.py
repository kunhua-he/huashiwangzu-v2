"""Service layer for wechat-writer module."""

import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text

from app.database import AsyncSessionLocal
from app.gateway.service import chat as gateway_chat
from app.services.file_reader import resolve_caller_user_id as resolve_user_id
from app.services.prompt_helpers import load_prompt_with_fallback

from .models import WechatDraft, WechatPrompt

logger = logging.getLogger("v2.wechat_writer").getChild("services")

MODULE_KEY = "wechat-writer"
WRITING_PROFILE = "deepseek-v4-flash"
# ── Prompt helpers ──────────────────────────────────────────────

async def get_prompt(db: AsyncSession, key: str, owner_id: int = 0) -> str | None:
    r = await db.execute(
        select(WechatPrompt).where(
            WechatPrompt.key == key,
            WechatPrompt.owner_id.in_([0, owner_id]),
            WechatPrompt.deleted == False,
        ).order_by(WechatPrompt.owner_id.desc()).limit(1)
    )
    prompt = r.scalar_one_or_none()
    return prompt.content if prompt else None


async def _load_prompt_with_fallback(db: AsyncSession, key: str, owner_id: int, **format_kwargs) -> str:
    return await load_prompt_with_fallback(
        db,
        key,
        owner_id,
        get_prompt,
        DEFAULT_FALLBACKS,
        logger=logger,
        **format_kwargs,
    )


DEFAULT_FALLBACKS = {
    "persona_system": "你是一个专业的问题肌修护专家。请用通俗易懂、亲切友好的语言回答问题。",
    "topic_generation": "请根据以下方向生成公众号选题建议：\n{direction}",
    "outline_generation": "请为以下选题生成公众号文章大纲：\n{topic}\n方向：{direction}",
    "article_generation": "请根据以下大纲撰写公众号文章：\n{topic}\n大纲：\n{outline}",
    "ingredient_validation": "请校验以下内容的科学准确性：\n{content}",
}


# ── Topic generation ────────────────────────────────────────────

async def generate_topics(direction: str, owner_id: int) -> list[dict]:
    async with AsyncSessionLocal() as db:
        system_prompt = await _load_prompt_with_fallback(db, "persona_system", owner_id)
        user_prompt = await _load_prompt_with_fallback(db, "topic_generation", owner_id, direction=direction)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await gateway_chat(messages, profile_key=WRITING_PROFILE)
    return {"topics": result.get("content", ""), "raw": result}


# ── Outline generation ──────────────────────────────────────────

async def generate_outline(topic: str, direction: str, owner_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        system_prompt = await _load_prompt_with_fallback(db, "persona_system", owner_id)
        user_prompt = await _load_prompt_with_fallback(db, "outline_generation", owner_id, topic=topic, direction=direction)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await gateway_chat(messages, profile_key=WRITING_PROFILE)
    return {"outline": result.get("content", ""), "raw": result}


# ── Article generation ──────────────────────────────────────────

async def generate_article(topic: str, outline: str, direction: str, owner_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        system_prompt = await _load_prompt_with_fallback(db, "persona_system", owner_id)
        user_prompt = await _load_prompt_with_fallback(db, "article_generation", owner_id, topic=topic, outline=outline)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await gateway_chat(messages, profile_key=WRITING_PROFILE)
    return {"article": result.get("content", ""), "raw": result}


# ── Ingredient/effect validation via knowledge search ──────────

async def validate_content(content: str, owner_id: int) -> dict:
    from app.services.module_registry import call_capability

    try:
        kb_result = await call_capability(
            "knowledge", "search",
            {"query": content, "top_k": 5},
            caller=f"user:{owner_id}",
            caller_role="viewer",
        )
        kb_results = kb_result.get("results", [])
        evidence_meta = kb_result.get("evidence_meta", {})
        has_knowledge = bool(kb_results)
    except Exception as exc:
        logger.warning("Knowledge search failed (may not have knowledge base): %s", exc)
        kb_results = []
        evidence_meta = {}
        has_knowledge = False

    # Also use AI to review the content
    async with AsyncSessionLocal() as db:
        validation_prompt = await _load_prompt_with_fallback(db, "ingredient_validation", owner_id, content=content)
        persona = await _load_prompt_with_fallback(db, "persona_system", owner_id)

    messages = [
        {"role": "system", "content": persona + "\n\n你现在要做成分科学审核。"},
        {"role": "user", "content": validation_prompt},
    ]
    ai_review = await gateway_chat(messages, profile_key=WRITING_PROFILE)

    return {
        "has_knowledge_base_results": has_knowledge,
        "knowledge_results": kb_results,
        "evidence_meta": evidence_meta,
        "ai_validation": ai_review.get("content", ""),
    }


# ── Draft CRUD ──────────────────────────────────────────────────

async def list_drafts(owner_id: int, page: int = 1, page_size: int = 20) -> dict:
    async with AsyncSessionLocal() as db:
        offset = (page - 1) * page_size
        r = await db.execute(
            select(WechatDraft).where(
                WechatDraft.owner_id == owner_id,
                WechatDraft.deleted == False,
            ).order_by(WechatDraft.updated_at.desc()).offset(offset).limit(page_size)
        )
        items = r.scalars().all()
        total_r = await db.execute(
            sa_text("SELECT COUNT(*) FROM wechat_drafts WHERE owner_id = :oid AND deleted = false"),
            {"oid": owner_id},
        )
        total = total_r.scalar() or 0
        return {
            "items": [_draft_to_dict(d) for d in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


async def get_draft(draft_id: int, owner_id: int) -> dict | None:
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(WechatDraft).where(
                WechatDraft.id == draft_id,
                WechatDraft.owner_id == owner_id,
                WechatDraft.deleted == False,
            )
        )
        d = r.scalar_one_or_none()
        return _draft_to_dict(d) if d else None


async def create_draft(data: dict, owner_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        draft = WechatDraft(
            owner_id=owner_id,
            title=data.get("title", ""),
            outline=data.get("outline"),
            content=data.get("content", ""),
            article_type=data.get("article_type", ""),
            keywords=data.get("keywords"),
            notes=data.get("notes", ""),
            status=data.get("status", "draft"),
            version=1,
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)
        return _draft_to_dict(draft)


async def update_draft(draft_id: int, data: dict, owner_id: int) -> dict | None:
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(WechatDraft).where(
                WechatDraft.id == draft_id,
                WechatDraft.owner_id == owner_id,
                WechatDraft.deleted == False,
            )
        )
        draft = r.scalar_one_or_none()
        if not draft:
            return None

        upd = {}
        for field in ("title", "outline", "content", "article_type", "keywords", "notes", "status"):
            if field in data:
                setattr(draft, field, data[field])
                upd[field] = data[field]
        if upd:
            draft.version += 1
            draft.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(draft)
        return _draft_to_dict(draft)


async def delete_draft(draft_id: int, owner_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(WechatDraft).where(
                WechatDraft.id == draft_id,
                WechatDraft.owner_id == owner_id,
                WechatDraft.deleted == False,
            )
        )
        draft = r.scalar_one_or_none()
        if not draft:
            return False
        draft.deleted = True
        await db.commit()
        return True


# ── Prompt CRUD ─────────────────────────────────────────────────

async def list_prompts(owner_id: int, category: str | None = None) -> list[dict]:
    async with AsyncSessionLocal() as db:
        query = select(WechatPrompt).where(
            WechatPrompt.owner_id.in_([0, owner_id]),
            WechatPrompt.deleted == False,
        )
        if category:
            query = query.where(WechatPrompt.category == category)
        query = query.order_by(WechatPrompt.category, WechatPrompt.key)
        r = await db.execute(query)
        items = r.scalars().all()
        seen = {}
        for p in items:
            seen[p.key] = p
        return [_prompt_to_dict(p) for p in seen.values()]


async def save_prompt(data: dict, owner_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        key = data.get("key", "")
        r = await db.execute(
            select(WechatPrompt).where(
                WechatPrompt.key == key,
                WechatPrompt.owner_id == owner_id,
                WechatPrompt.deleted == False,
            )
        )
        existing = r.scalar_one_or_none()
        if existing:
            existing.content = data.get("content", existing.content)
            existing.name = data.get("name", existing.name)
            existing.description = data.get("description", existing.description)
            existing.category = data.get("category", existing.category)
            existing.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(existing)
            return _prompt_to_dict(existing)
        else:
            prompt = WechatPrompt(
                owner_id=owner_id,
                key=key,
                name=data.get("name", key),
                content=data.get("content", ""),
                description=data.get("description", ""),
                category=data.get("category", "custom"),
            )
            db.add(prompt)
            await db.commit()
            await db.refresh(prompt)
            return _prompt_to_dict(prompt)


async def delete_prompt(prompt_id: int, owner_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(WechatPrompt).where(
                WechatPrompt.id == prompt_id,
                WechatPrompt.owner_id == owner_id,
                WechatPrompt.deleted == False,
            )
        )
        p = r.scalar_one_or_none()
        if not p:
            return False
        p.deleted = True
        await db.commit()
        return True


# ── Helpers ─────────────────────────────────────────────────────

def _draft_to_dict(d: WechatDraft) -> dict:
    return {
        "id": d.id,
        "owner_id": d.owner_id,
        "title": d.title,
        "outline": d.outline,
        "content": d.content,
        "article_type": d.article_type,
        "keywords": d.keywords,
        "notes": d.notes,
        "status": d.status,
        "version": d.version,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _prompt_to_dict(p: WechatPrompt) -> dict:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "key": p.key,
        "name": p.name,
        "content": p.content,
        "description": p.description,
        "category": p.category,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
