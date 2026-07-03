"""Resource service — content-addressed resource store.

Images, audio, video, rendered pages, and other binary resources
are stored here with deduplication by content hash.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFound
from app.models.content import Resource, ResourceRef

logger = logging.getLogger("v2.content").getChild("resource")


class ResourceService:

    STORAGE_PREFIX = "res"

    async def create_resource(
        self, db: AsyncSession, data: bytes, owner_id: int,
        resource_type: str = "binary", mime_type: str = "application/octet-stream",
        filename: str = "",
        width: int | None = None, height: int | None = None,
        description: str | None = None, ocr_text: str | None = None,
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(data).hexdigest()
        existing = await self._find_by_hash(db, content_hash, owner_id=owner_id)
        if existing:
            existing.ref_count += 1
            await db.commit()
            return self._to_dict(existing)

        stored_hash = content_hash
        global_existing = await self._find_by_hash(db, content_hash)
        if global_existing and global_existing.owner_id != owner_id:
            stored_hash = hashlib.sha256(f"{owner_id}:{content_hash}".encode()).hexdigest()

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        storage_path = f"{self.STORAGE_PREFIX}/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}.{ext}"
        upload_root = Path(get_settings().UPLOAD_DIR).resolve()
        abs_path = upload_root / storage_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)

        resource = Resource(
            owner_id=owner_id,
            hash=stored_hash,
            hash_algorithm="sha256",
            resource_type=resource_type,
            mime_type=mime_type,
            storage_path=storage_path,
            file_size=len(data),
            width=width,
            height=height,
            description=description,
            ocr_text=ocr_text,
            ref_count=1,
        )
        db.add(resource)
        await db.commit()
        await db.refresh(resource)
        return self._to_dict(resource)

    async def create_resource_from_file(
        self, db: AsyncSession, file_id: int, owner_id: int,
        resource_type: str | None = None,
    ) -> dict[str, Any]:
        from app.services.file_service import check_file_access, get_file_record
        file_record = await get_file_record(db, file_id)
        if not file_record:
            raise NotFound(f"File {file_id} not found")

        await check_file_access(db, file_id, owner_id)

        from app.services.file_preview_service import _resolve_storage_path
        safe_path = _resolve_storage_path(file_record)
        if not safe_path:
            raise NotFound("File not found on disk")

        data = Path(safe_path).read_bytes()
        ext = (file_record.extension or "").lower()
        rtype = resource_type or _detect_resource_type(ext)
        filename = f"{file_record.name}.{file_record.extension}" if file_record.extension else file_record.name

        return await self.create_resource(
            db, data, owner_id,
            resource_type=rtype,
            mime_type=file_record.mime_type or "application/octet-stream",
            filename=filename,
        )

    async def get_resource(self, db: AsyncSession, resource_id: int) -> dict[str, Any]:
        resource = await db.get(Resource, resource_id)
        if not resource:
            raise NotFound(f"Resource {resource_id} not found")
        return self._to_dict(resource)

    async def get_resource_bytes(self, db: AsyncSession, resource_id: int) -> tuple[bytes, str]:
        resource = await db.get(Resource, resource_id)
        if not resource:
            raise NotFound(f"Resource {resource_id} not found")
        upload_root = Path(get_settings().UPLOAD_DIR).resolve()
        abs_path = upload_root / resource.storage_path
        if not abs_path.exists():
            raise NotFound("Resource file not found on disk")
        return abs_path.read_bytes(), resource.mime_type

    async def update_description(
        self, db: AsyncSession, resource_id: int,
        description: str | None = None,
        ocr_text: str | None = None,
        vlm_metadata: dict | None = None,
    ) -> dict[str, Any]:
        resource = await db.get(Resource, resource_id)
        if not resource:
            raise NotFound(f"Resource {resource_id} not found")
        if description is not None:
            resource.description = description
        if ocr_text is not None:
            resource.ocr_text = ocr_text
        if vlm_metadata is not None:
            import json
            resource.vlm_metadata = json.dumps(vlm_metadata, ensure_ascii=False)
        await db.commit()
        await db.refresh(resource)
        return self._to_dict(resource)

    async def add_ref(
        self, db: AsyncSession, package_id: int, resource_id: int,
        block_id: str | None = None, usage_type: str = "embedded",
        page: int | None = None, coordinates: dict | None = None,
        usage_hints: str | None = None,
        version_id: int | None = None,
    ) -> dict[str, Any]:
        existing_result = await db.execute(
            select(ResourceRef).where(
                ResourceRef.package_id == package_id,
                ResourceRef.resource_id == resource_id,
            ).limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            if version_id is not None and existing.version_id is None:
                existing.version_id = version_id
            if block_id is not None and not existing.block_id:
                existing.block_id = block_id
            if page is not None and existing.page is None:
                existing.page = page
            if coordinates is not None and not existing.coordinates:
                existing.coordinates = json.dumps(coordinates, ensure_ascii=False)
            if usage_hints is not None and not existing.usage_hints:
                existing.usage_hints = usage_hints
            await db.commit()
            await db.refresh(existing)
            return self._ref_to_dict(existing)

        ref = ResourceRef(
            package_id=package_id,
            version_id=version_id,
            resource_id=resource_id,
            block_id=block_id,
            usage_type=usage_type,
            page=page,
            coordinates=json.dumps(coordinates, ensure_ascii=False) if coordinates else None,
            usage_hints=usage_hints,
        )
        db.add(ref)
        await db.commit()
        await db.refresh(ref)
        return self._ref_to_dict(ref)

    async def find_resources_by_block(
        self, db: AsyncSession, package_id: int, block_id: str,
    ) -> list[dict]:
        result = await db.execute(
            select(ResourceRef).where(
                ResourceRef.package_id == package_id,
                ResourceRef.block_id == block_id,
            )
        )
        refs = result.scalars().all()
        return [self._ref_to_dict(r) for r in refs]

    async def _find_by_hash(
        self,
        db: AsyncSession,
        content_hash: str,
        owner_id: int | None = None,
    ) -> Resource | None:
        query = select(Resource).where(Resource.hash == content_hash)
        if owner_id is not None:
            owner_hash = hashlib.sha256(f"{owner_id}:{content_hash}".encode()).hexdigest()
            query = select(Resource).where(
                Resource.owner_id == owner_id,
                Resource.hash.in_([content_hash, owner_hash]),
            )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    def _to_dict(self, r: Resource) -> dict:
        vlm = r.vlm_metadata
        if isinstance(vlm, str):
            try:
                vlm = json.loads(vlm)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "id": r.id,
            "owner_id": r.owner_id,
            "hash": r.hash,
            "hash_algorithm": r.hash_algorithm,
            "resource_type": r.resource_type,
            "mime_type": r.mime_type,
            "storage_path": r.storage_path,
            "file_size": r.file_size,
            "width": r.width,
            "height": r.height,
            "duration_ms": r.duration_ms,
            "description": r.description,
            "ocr_text": r.ocr_text,
            "vlm_metadata": vlm,
            "ref_count": r.ref_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    def _ref_to_dict(self, ref: ResourceRef) -> dict:
        coords = ref.coordinates
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "id": ref.id,
            "package_id": ref.package_id,
            "version_id": ref.version_id,
            "resource_id": ref.resource_id,
            "block_id": ref.block_id,
            "usage_type": ref.usage_type,
            "page": ref.page,
            "coordinates": coords,
            "usage_hints": ref.usage_hints,
            "created_at": ref.created_at.isoformat() if ref.created_at else None,
        }


def _detect_resource_type(extension: str) -> str:
    ext = extension.lower()
    if ext in {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "tiff"}:
        return "image"
    if ext in {"mp4", "avi", "mov", "mkv", "webm"}:
        return "video"
    if ext in {"mp3", "wav", "flac", "aac", "ogg", "wma"}:
        return "audio"
    if ext == "pdf":
        return "document"
    return "binary"
