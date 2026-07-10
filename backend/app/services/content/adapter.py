"""Content export adapters — call format-specific modules to produce physical files.

Routes export requests to the right module (office-gen, pdf module, etc.)
while keeping the Content Package as the single canonical source.
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.module_registry import call_capability_as_system

logger = logging.getLogger("v2.content").getChild("adapter")


async def call_export_adapter(
    db: AsyncSession,
    adapter_type: str,
    payload: dict,
    owner_id: int,
) -> dict[str, Any]:
    if adapter_type in ("docx", "xlsx", "pptx", "pdf"):
        module_key = "office-gen"
        action = adapter_type
        logger.info("Export adapter: calling %s:%s", module_key, action)
        try:
            result = await call_capability_as_system(
                module_key, action,
                payload,
                principal="system:content-service",
                on_behalf_of_user_id=owner_id,
            )
        except Exception as e:
            logger.warning("Export adapter %s failed: %s. Falling back to text.", adapter_type, e)
            return {"fallback": True}

        file_id = None
        if isinstance(result, dict):
            file_id = result.get("file_id")
        if file_id:
            from app.services.file_preview_service import _resolve_storage_path
            from app.services.file_service import check_file_access

            file_record = await check_file_access(db, file_id, owner_id)
            safe_path = _resolve_storage_path(file_record)
            if safe_path:
                return {"file_path": str(safe_path), "file_id": file_id}
        return result

    return {"fallback": True}
