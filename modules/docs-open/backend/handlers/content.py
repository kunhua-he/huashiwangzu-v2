"""Content read/write operations for docs-open module.

All public content is now exchanged as DocumentIR — the unified
document intermediate representation shared by all parsers, office
package, office-gen, and knowledge ingestion.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.config import get_settings
from app.core.exceptions import AppException
from app.schemas.document_ir import DocumentIR, BlockIR, ManifestIR, ResourceIR

from .embed import _get_doc_type


async def _read_ir_from_parser(db: AsyncSession, file: File, module_key: str,
                                user_role: str = "editor") -> dict | None:
    """Call a parser module capability and return its DocumentIR dict."""
    from app.services.module_registry import call_capability
    try:
        result = await call_capability(
            module_key, "parse",
            {"file_id": file.id},
            caller=f"user:{file.owner_id}",
            caller_role=user_role,
        )
        return result
    except Exception as e:
        return None


async def _read_content(db: AsyncSession, file: File, ext: str, user_role: str = "editor") -> dict:
    """Read document content as unified DocumentIR based on file type.

    Delegates to registered parser capabilities where available.
    Falls back to a direct read for simple text formats.
    """
    settings = get_settings()
    storage_root = Path(settings.UPLOAD_DIR).resolve()
    full_path = (storage_root / file.storage_path).resolve()

    parser_map = {
        "md": "text-parser",
        "markdown": "text-parser",
        "txt": "text-parser",
        "pdf": "pdf-parser",
        "docx": "docx-parser",
        "pptx": "pptx-parser",
        "xlsx": "excel-engine",
        "xls": "excel-engine",
    }
    if ext in parser_map:
        result = await _read_ir_from_parser(db, file, parser_map[ext], user_role)
        if result:
            return result

    if ext in ("txt", "md", "markdown", "json", "yaml", "yml", "xml", "ini", "cfg", "log"):
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        blocks = [{"type": "paragraph", "text": line.strip(), "page": None, "resource_ref": None}
                  for line in text.splitlines() if line.strip()]
        ir = DocumentIR(
            file_id=file.id, format=ext,
            manifest=ManifestIR(file_name=file.name, file_type=ext),
            blocks=blocks,
        )
        return ir.model_dump(exclude_none=True)

    if ext == "csv":
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        import csv, io
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return {
            "file_id": file.id, "format": ext,
            "manifest": {"file_name": file.name, "file_type": ext},
            "blocks": [{"type": "table", "text": str(rows), "page": None, "resource_ref": None}],
            "resources": [],
        }

    return {
        "file_id": file.id, "format": ext,
        "manifest": {"file_name": file.name, "file_type": ext},
        "blocks": [],
        "resources": [],
    }


async def _write_content(db: AsyncSession, file: File, ext: str,
                         content: dict | list | str, user_role: str = "editor") -> None:
    """Write content (DocumentIR or plain text) back to a document.

    Accepts either a full DocumentIR dict or a format-specific payload.
    For DocumentIR input, it projects blocks to the target format via
    the appropriate office-gen capability.
    """
    from app.services.file_upload_service import replace_file_content

    is_document_ir = isinstance(content, dict) and "file_id" in content and "blocks" in content
    blocks = content.get("blocks", []) if is_document_ir else None
    manifest = content.get("manifest", {}) if is_document_ir else {}

    if ext in ("txt", "md", "json", "yaml", "yml", "xml", "ini", "cfg", "log"):
        if is_document_ir and blocks:
            text = "\n\n".join(
                b.get("text", "") for b in blocks if b.get("type") in ("paragraph", "heading")
            )
        else:
            text = content if isinstance(content, str) else str(content)
        await replace_file_content(db, file.id, file.owner_id, text.encode("utf-8"))

    elif ext in ("xlsx", "xls"):
        try:
            from app.services.module_registry import call_capability
            json_str = __import__("json").dumps(content, ensure_ascii=False)
            await call_capability(
                "office-gen", "xlsx",
                {"filename": file.name, "content": json_str},
                caller=f"user:{file.owner_id}",
                caller_role="admin",
            )
        except Exception as e:
            raise AppException(f"Failed to write xlsx: {e}", status_code=500)

    elif ext in ("docx",):
        try:
            from app.services.module_registry import call_capability
            docx_payload = content
            if is_document_ir and blocks:
                docx_payload = {
                    "manifest": manifest,
                    "blocks": blocks,
                    "resources": content.get("resources", []),
                }
            await call_capability(
                "office-gen", "docx",
                {"filename": file.name, "content": docx_payload},
                caller=f"user:{file.owner_id}",
                caller_role="admin",
            )
        except Exception as e:
            raise AppException(f"Failed to write docx: {e}", status_code=500)

    elif ext == "csv":
        text = content if isinstance(content, str) else str(content)
        await replace_file_content(db, file.id, file.owner_id, text.encode("utf-8"))

    else:
        raise AppException(f"Writing to {ext} is not supported yet", status_code=400)
