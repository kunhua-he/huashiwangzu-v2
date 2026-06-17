from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import DisambigCandidate, Entity, EntityAlias


def entity_item(entity: Entity, aliases: list[EntityAlias] | None = None) -> dict:
    active_aliases = [a for a in aliases or [] if a.alias_type != "disabled"]
    return {
        "dictionary_id": entity.id,
        "standard_name": entity.standard_name,
        "entity_type": entity.entity_type,
        "description": None,
        "status": entity.confirm_status,
        "alias_list": [a.alias for a in active_aliases],
        "creator_id": None,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def alias_item(alias: EntityAlias) -> dict:
    return {
        "alias_id": alias.id,
        "dictionary_id": alias.entity_id,
        "alias_name": alias.alias,
        "status": alias.alias_type,
        "created_at": alias.created_at.isoformat() if alias.created_at else None,
    }


async def load_alias_map(db: AsyncSession, entity_ids: list[int]) -> dict[int, list[EntityAlias]]:
    if not entity_ids:
        return {}
    rows = (await db.execute(select(EntityAlias).where(EntityAlias.entity_id.in_(entity_ids)))).scalars().all()
    result: dict[int, list[EntityAlias]] = {}
    for alias in rows:
        result.setdefault(alias.entity_id, []).append(alias)
    return result


async def load_entities(db: AsyncSession, entity_ids: set[int]) -> dict[int, Entity]:
    if not entity_ids:
        return {}
    rows = (await db.execute(select(Entity).where(Entity.id.in_(entity_ids)))).scalars().all()
    return {entity.id: entity for entity in rows}


def page_info(data: dict) -> dict:
    page_size = data["pageSize"]
    total_pages = (data["total"] + page_size - 1) // page_size if page_size else 0
    return {
        "current_page": data["page"],
        "page_size": page_size,
        "total": data["total"],
        "total_pages": total_pages,
    }


def disambig_item(item: DisambigCandidate, entities: dict[int, Entity]) -> dict:
    first = entities.get(item.entity_a_id)
    second = entities.get(item.entity_b_id)
    candidates = [{"dictionary_id": e.id, "standard_name": e.standard_name, "context_hint": ""} for e in [first, second] if e]
    names = [entity.standard_name for entity in [first, second] if entity]
    return {
        "disambiguation_id": item.id,
        "ambiguous_keyword": " / ".join(names) or f"Disambiguation {item.id}",
        "candidate_entities": candidates,
        "related_dictionary_ids": [item.entity_a_id, item.entity_b_id],
        "processing_status": item.review_status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
