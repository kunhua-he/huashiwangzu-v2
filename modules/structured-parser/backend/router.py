import json

from app.core.exceptions import ValidationError
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_reader import decode_text_bytes
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/structured-parser", tags=["structured-parser"])


class ParseRequest(BaseModel):
    file_id: int


def _flatten_json(obj: object, prefix: str = "", depth: int = 0, max_depth: int = 10) -> list[str]:
    if depth > max_depth:
        return [f"{prefix}: (max depth reached)"]
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                lines.extend(_flatten_json(v, path, depth + 1, max_depth))
            else:
                lines.append(f"{path}: {v}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                lines.extend(_flatten_json(item, path, depth + 1, max_depth))
            else:
                lines.append(f"{path}: {item}")
    else:
        lines.append(f"{prefix}: {obj}")
    return lines


async def _parse(params: dict, caller: str) -> dict:
    allowed = {"json", "yaml", "yml"}

    def parse_file(file_id, _file, full_path, ext):
        content = decode_text_bytes(full_path.read_bytes())

        blocks = []
        content = content.strip()
        if not content:
            return {"file_id": file_id, "format": ext, "blocks": [], "resources": []}

        data: object = None
        if ext in ("yaml", "yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                raise ValidationError("YAML parsing requires PyYAML library")
            except Exception as e:
                raise ValidationError(f"Invalid YAML: {e}")
        else:
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON: {e}")

        lines = _flatten_json(data)
        if lines:
            summary = f"结构化数据：{len(lines)} 个字段"
            blocks.append({"type": "段落", "text": summary, "page": None, "resource_ref": None})

            batch_size = 30
            for start in range(0, len(lines), batch_size):
                batch = lines[start:start + batch_size]
                blocks.append({
                    "type": "段落",
                    "text": "\n".join(batch),
                    "page": None,
                    "resource_ref": None,
                })

        return {
            "file_id": file_id,
            "format": ext,
            "blocks": blocks,
            "resources": [],
        }

    return await run_uploaded_file_capability(params, caller, allowed, parse_file)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "structured-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "structured-parser", "parse", _parse,
    description="Parse JSON/YAML files into unified content blocks",
    brief="解析 JSON/YAML 结构化文件",
    parameters={"file_id": {"type": "int", "description": "File ID in file storage"}},
    min_role="viewer",
)
