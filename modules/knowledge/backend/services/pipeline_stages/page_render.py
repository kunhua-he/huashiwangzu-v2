"""Page render and asset materialization stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..page_asset_service import materialize_page_assets_stage


async def run(db: AsyncSession, *, doc: KbDocument, user_id: int, **_: object) -> dict:
    return await materialize_page_assets_stage(db, int(doc.id), int(doc.owner_id), int(doc.file_id), int(user_id))
