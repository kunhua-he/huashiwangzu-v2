"""Cross-module capability registration for docs-open.

注册：docs-open:open, docs-open:get_content, docs-open:create_doc.
"""

from __future__ import annotations

from app.services.module_registry import register_capability
from app.services.file_reader import resolve_caller_user_id

from .embed import _get_doc_type
from .content import _read_content


async def _open_capability(params: dict, caller: str) -> dict:
    file_id = int(params.get("file_id", 0))
    mode = params.get("mode", "view")
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    from app.database import AsyncSessionLocal
    from app.models.file import File
    from app.services.file_service import check_file_access

    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        file = await check_file_access(db, file_id, user_id)
        ext = (file.extension or "").lower().lstrip(".")
        doc_info = _get_doc_type(ext)
        return {
            "id": str(file.id),
            "title": file.name,
            "type": ext,
            "category": doc_info.get("category"),
            "editor": doc_info.get("editor"),
            "mime": doc_info.get("mime"),
        }


async def _get_content_capability(params: dict, caller: str) -> dict:
    file_id = int(params.get("file_id", 0))
    if file_id <= 0:
        raise ValueError("file_id must be a positive integer")

    from app.database import AsyncSessionLocal
    from app.models.file import File
    from app.services.file_service import check_file_access

    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        file = await check_file_access(db, file_id, user_id)
        ext = (file.extension or "").lower().lstrip(".")
        return await _read_content(db, file, ext)


async def _create_doc_capability(params: dict, caller: str) -> dict:
    title = params.get("title", "untitled")
    doc_type = params.get("type", "txt")
    from app.database import AsyncSessionLocal
    user_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        from app.services import file_create_service
        result = await file_create_service.create_file(db, title, doc_type, user_id, None)
        return {"id": str(result["id"]), "title": title, "type": doc_type}


# ── Register capabilities ──

register_capability(
    "docs-open", "open", _open_capability,
    description="Open a document by file_id, returns metadata and editor info",
    brief="打开文档",
    parameters={"file_id": {"type": "int"}, "mode": {"type": "string"}},
    min_role="viewer",
)

register_capability(
    "docs-open", "get_content", _get_content_capability,
    description="Get structured JSON content of a document by file_id",
    brief="获取文档内容",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)

register_capability(
    "docs-open", "create_doc", _create_doc_capability,
    description="Create a new empty document",
    brief="创建文档",
    parameters={"title": {"type": "string"}, "type": {"type": "string"}},
    min_role="editor",
)
