"""Content Package REST endpoints."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.content_package import (
    BlockAppendRequest,
    BlockUpdateRequest,
    ExportRequest,
    PublishRequest,
    ReplaceTextRequest,
)
from app.services.content.export_service import ContentExportService
from app.services.content.package_service import ContentPackageService
from app.services.content.pipeline_service import ContentPipelineService
from app.services.content.resource_service import ResourceService
from app.services.file_reader import resolve_caller_user_id
from app.services.module_registry import register_capability

logger = logging.getLogger("v2.content")

router = APIRouter(prefix="/api/content", tags=["content"])

pkg_svc = ContentPackageService()
pipeline_svc = ContentPipelineService()
export_svc = ContentExportService()
resource_svc = ResourceService()


# ── Schemas ──────────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    file_id: int


class PackageQuery(BaseModel):
    package_id: int | None = None
    file_id: int | None = None


class UpdateBlocksRequest(BaseModel):
    package_id: int
    updates: list[BlockUpdateRequest]


class AppendBlocksRequest(BaseModel):
    package_id: int
    blocks: list[BlockAppendRequest]


class ReplaceTextBody(BaseModel):
    package_id: int
    request: ReplaceTextRequest


class VersionRestoreRequest(BaseModel):
    package_id: int
    version_id: int


# ── REST Endpoints ───────────────────────────────────────────────

@router.post("/pipeline")
async def trigger_pipeline(
    body: PipelineRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    caller = f"user:{user.id}"
    result = await pipeline_svc.run_pipeline(body.file_id, caller)
    return ApiResponse(data=result)


@router.get("/packages")
async def list_packages(
    file_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    if file_id:
        pkg = await pkg_svc.get_package(db, file_id=file_id, owner_id=user.id)
        return ApiResponse(data=pkg)
    return ApiResponse(data={"packages": []})


@router.get("/packages/{package_id}")
async def get_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.get_package(db, package_id=package_id, owner_id=user.id)
    return ApiResponse(data=result)


@router.get("/packages/{package_id}/full")
async def get_full_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.get_full_package(db, package_id=package_id, owner_id=user.id)
    return ApiResponse(data=result)


@router.get("/packages/{package_id}/blocks")
async def list_blocks(
    package_id: int,
    block_type: str | None = None,
    page: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.list_blocks(
        db, package_id, block_type=block_type, page=page, owner_id=user.id,
    )
    return ApiResponse(data={"blocks": result})


@router.get("/packages/{package_id}/blocks/{block_id}")
async def get_block(
    package_id: int, block_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.get_block(db, package_id, block_id, owner_id=user.id)
    return ApiResponse(data=result)


@router.put("/packages/{package_id}/blocks")
async def update_blocks(
    package_id: int,
    body: UpdateBlocksRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    caller = f"user:{user.id}"
    result = await pkg_svc.update_blocks(db, package_id, body.updates, caller, owner_id=user.id)
    return ApiResponse(data=result)


@router.post("/packages/{package_id}/blocks")
async def append_blocks(
    package_id: int,
    body: AppendBlocksRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    caller = f"user:{user.id}"
    result = await pkg_svc.append_blocks(db, package_id, body.blocks, caller, owner_id=user.id)
    return ApiResponse(data=result)


@router.post("/packages/{package_id}/replace-text")
async def replace_text(
    package_id: int,
    body: ReplaceTextBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    caller = f"user:{user.id}"
    result = await pkg_svc.replace_text(db, package_id, body.request, caller, owner_id=user.id)
    return ApiResponse(data=result)


@router.get("/packages/{package_id}/versions")
async def list_versions(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.list_versions(db, package_id, owner_id=user.id)
    return ApiResponse(data={"versions": result})


@router.post("/packages/{package_id}/restore")
async def restore_version(
    package_id: int,
    body: VersionRestoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    caller = f"user:{user.id}"
    result = await pkg_svc.restore_version(db, package_id, body.version_id, caller, owner_id=user.id)
    return ApiResponse(data=result)


@router.get("/packages/{package_id}/resources")
async def list_resources(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.list_resources(db, package_id, owner_id=user.id)
    return ApiResponse(data={"resources": result})


@router.get("/resources/{resource_id}")
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await pkg_svc.get_resource(db, resource_id, owner_id=user.id)
    return ApiResponse(data=result)


@router.post("/packages/{package_id}/export")
async def export_package(
    package_id: int,
    body: ExportRequest = ExportRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await export_svc.export(
        db, package_id,
        target_format=body.target_format,
        owner_id=user.id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.post("/packages/{package_id}/publish")
async def publish_package(
    package_id: int,
    body: PublishRequest = PublishRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await export_svc.publish(
        db, package_id,
        target_file_id=body.target_file_id,
        owner_id=user.id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await pkg_svc.delete_package(db, package_id, owner_id=user.id)
    return ApiResponse(data=result)


# ── Capability handlers ──────────────────────────────────────────

async def _cap_pipeline(params: dict, caller: str) -> dict:
    file_id = params.get("file_id")
    if not file_id:
        return {"success": False, "error": "file_id required"}
    try:
        result = await pipeline_svc.run_pipeline(file_id, caller)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _cap_get_package(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    file_id = params.get("file_id")
    if not package_id and not file_id:
        return {"success": False, "error": "package_id or file_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.get_package(db, package_id=package_id, file_id=file_id, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_get_full(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.get_full_package(db, package_id, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_list_blocks(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    block_type = params.get("block_type")
    page = params.get("page")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.list_blocks(db, package_id, block_type=block_type, page=page, owner_id=owner_id)
            return {"success": True, "data": {"blocks": result}}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_get_block(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    block_id = params.get("block_id")
    if not package_id or not block_id:
        return {"success": False, "error": "package_id and block_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.get_block(db, package_id, block_id, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_update_blocks(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    updates_data = params.get("updates", [])
    if not package_id or not updates_data:
        return {"success": False, "error": "package_id and updates required"}
    owner_id = resolve_caller_user_id(caller)
    updates = [BlockUpdateRequest(**u) for u in updates_data]
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.update_blocks(db, package_id, updates, caller, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_append_blocks(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    blocks_data = params.get("blocks", [])
    if not package_id or not blocks_data:
        return {"success": False, "error": "package_id and blocks required"}
    owner_id = resolve_caller_user_id(caller)
    blocks = [BlockAppendRequest(**b) for b in blocks_data]
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.append_blocks(db, package_id, blocks, caller, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_replace_text(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    req_data = params.get("request", {})
    if not package_id or not req_data:
        return {"success": False, "error": "package_id and request required"}
    owner_id = resolve_caller_user_id(caller)
    req = ReplaceTextRequest(**req_data)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.replace_text(db, package_id, req, caller, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_export(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    target_format = params.get("target_format")
    conflict_policy = params.get("conflict_policy", "auto_rename")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await export_svc.export(
                db,
                package_id,
                target_format=target_format,
                owner_id=owner_id,
                conflict_policy=conflict_policy,
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_publish(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    target_file_id = params.get("target_file_id")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await export_svc.publish(db, package_id, target_file_id=target_file_id, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_list_versions(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.list_versions(db, package_id, owner_id=owner_id)
            return {"success": True, "data": {"versions": result}}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_restore_version(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    version_id = params.get("version_id")
    if not package_id or not version_id:
        return {"success": False, "error": "package_id and version_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.restore_version(db, package_id, version_id, caller, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_list_resources(params: dict, caller: str) -> dict:
    package_id = params.get("package_id")
    if not package_id:
        return {"success": False, "error": "package_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.list_resources(db, package_id, owner_id=owner_id)
            return {"success": True, "data": {"resources": result}}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_get_resource(params: dict, caller: str) -> dict:
    resource_id = params.get("resource_id")
    if not resource_id:
        return {"success": False, "error": "resource_id required"}
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await pkg_svc.get_resource(db, resource_id, owner_id=owner_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def _cap_store_resource(params: dict, caller: str) -> dict:
    """Store an extracted embedded resource (image/attachment) from a parser module.

    Parser modules call this capability after extracting binary data from Office/PDF files.
    The resource is stored content-addressed, deduplicated by sha256.
    """
    data_b64 = params.get("data_b64")
    if not data_b64:
        return {"success": False, "error": "data_b64 required"}
    import base64
    data = base64.b64decode(data_b64)
    owner_id = resolve_caller_user_id(caller)
    async with AsyncSessionLocal() as db:
        try:
            result = await resource_svc.create_resource(
                db, data,
                owner_id=owner_id,
                resource_type=params.get("resource_type", "image"),
                mime_type=params.get("mime_type", "application/octet-stream"),
                filename=params.get("filename", "resource.bin"),
                width=params.get("width"),
                height=params.get("height"),
                description=params.get("description"),
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Event handler: file.uploaded → content pipeline ─────────────

async def _on_file_uploaded(payload: dict, caller: str, caller_role: str) -> dict:
    file_id = payload.get("file_id")
    if not file_id:
        return {"success": False, "error": "file_id required"}
    try:
        result = await pipeline_svc.handle_file_uploaded(payload, caller, caller_role)
        return {"success": True, "data": result}
    except Exception as e:
        logger.warning("Content pipeline from file.uploaded failed: %s", e)
        return {"success": False, "error": str(e)}


from app.services.module_events import register_module_event_handler

register_module_event_handler("file.uploaded", _on_file_uploaded, "content")

# ── Register capabilities ────────────────────────────────────────

def register_content_capabilities():
    caps = [
        ("pipeline", _cap_pipeline, "Automated content pipeline: parse file → content package", {"file_id": "int"}),
        ("get_package", _cap_get_package, "Get content package metadata", {"package_id": "int (optional)", "file_id": "int (optional)"}),
        ("get_full_package", _cap_get_full, "Get full content package with blocks and resource refs", {"package_id": "int"}),
        ("list_blocks", _cap_list_blocks, "List blocks in a content package", {"package_id": "int", "block_type": "str (optional)", "page": "int (optional)"}),
        ("get_block", _cap_get_block, "Get a single block by ID", {"package_id": "int", "block_id": "str"}),
        ("update_blocks", _cap_update_blocks, "Update one or more blocks", {"package_id": "int", "updates": "list[{block_id, text?, data?, style?}]"}),
        ("append_blocks", _cap_append_blocks, "Append new blocks to a package", {"package_id": "int", "blocks": "list[{type, text, data?, style?}]"}),
        ("replace_text", _cap_replace_text, "Find and replace text across blocks", {"package_id": "int", "request": "{old_text, new_text, scope}"}),
        ("export", _cap_export, "Export content package to a physical file", {"package_id": "int", "target_format": "str (optional)"}),
        ("publish", _cap_publish, "Publish content package as an artifact", {"package_id": "int", "target_file_id": "int (optional)"}),
        ("list_versions", _cap_list_versions, "List all versions of a content package", {"package_id": "int"}),
        ("restore_version", _cap_restore_version, "Restore a previous version", {"package_id": "int", "version_id": "int"}),
        ("list_resources", _cap_list_resources, "List resources referenced by a package", {"package_id": "int"}),
        ("get_resource", _cap_get_resource, "Get resource metadata by ID", {"resource_id": "int"}),
        ("store_resource", _cap_store_resource, "Store an extracted embedded resource (data_b64, mime_type, filename)", {"data_b64": "string", "resource_type": "string", "mime_type": "string", "filename": "string", "description": "string (optional)"}),
    ]
    for action, handler, desc, params in caps:
        role = "viewer" if action in ("get_package", "get_full_package", "list_blocks", "get_block", "list_versions", "list_resources", "get_resource") else "editor"
        register_capability(
            "content", action, handler,
            description=desc,
            parameters=params,
            min_role=role,
        )
    logger.info("Registered %d content:* capabilities", len(caps))


register_content_capabilities()
