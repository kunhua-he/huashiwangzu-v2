from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.database import get_db
from app.middleware.auth import require_permission
from app.models.knowledge import DisambigCandidate, Entity, EntityAlias
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.knowledge.dictionary_presenter import (
    alias_item,
    disambig_item,
    entity_item,
    load_alias_map,
    load_entities,
    page_info,
)
from app.services.knowledge.governance_presenter import paginate

router = APIRouter(prefix="/api/knowledge/dictionary", tags=["knowledge-dictionary"])


@router.get("/entities")
async def list_entities(
    keyword: str | None = None,
    entity_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
) -> ApiResponse:
    query = select(Entity).order_by(Entity.id.desc())
    if keyword:
        query = query.where(Entity.standard_name.ilike(f"%{keyword}%"))
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if status:
        query = query.where(Entity.confirm_status == status)
    data = await paginate(db, query, page, pageSize)
    alias_map = await load_alias_map(db, [entity.id for entity in data["items"]])
    return ApiResponse(data={
        "items": [entity_item(entity, alias_map.get(entity.id, [])) for entity in data["items"]],
        "pagination": page_info(data),
    })


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
) -> ApiResponse:
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise NotFound("Entity not found")
    result = await db.execute(select(EntityAlias).where(EntityAlias.entity_id == entity_id))
    aliases = result.scalars().all()
    data = entity_item(entity, aliases)
    data["aliases"] = [alias_item(alias) for alias in aliases]
    data["relations"] = {"has_disambiguation_record": False, "has_merge_record": False}
    return ApiResponse(data=data)


@router.get("/disambiguation")
async def list_disambiguation(
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
) -> ApiResponse:
    query = select(DisambigCandidate).order_by(DisambigCandidate.id.desc())
    if status:
        query = query.where(DisambigCandidate.review_status == status)
    data = await paginate(db, query, page, pageSize)
    entity_ids = {i.entity_a_id for i in data["items"]} | {i.entity_b_id for i in data["items"]}
    entities = await load_entities(db, entity_ids)
    rows = [disambig_item(i, entities) for i in data["items"]]
    if keyword:
        rows = [row for row in rows if keyword in row["ambiguous_keyword"]]
    return ApiResponse(data={"items": rows, "pagination": page_info(data)})


@router.post("/disambiguation/{candidate_id}/approve")
async def approve_disambiguation(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
) -> ApiResponse:
    return await set_disambiguation_status(db, candidate_id, "approved")


@router.post("/disambiguation/{candidate_id}/reject")
async def reject_disambiguation(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
) -> ApiResponse:
    return await set_disambiguation_status(db, candidate_id, "rejected")


async def set_disambiguation_status(db: AsyncSession, candidate_id: int, status: str) -> ApiResponse:
    candidate = await db.get(DisambigCandidate, candidate_id)
    if not candidate:
        raise NotFound("Disambiguation candidate not found")
    candidate.review_status = status
    await db.commit()
    return ApiResponse(data={"disambiguation_id": candidate_id, "processing_status": status})
