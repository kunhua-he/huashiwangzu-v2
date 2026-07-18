from app.core.exceptions import ValidationError
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .parser import SUPPORTED_EXTS, CodeParseError, parse_code_file

router = APIRouter(prefix="/api/code-generic-parser", tags=["code-generic-parser"])


class ParseRequest(BaseModel):
    file_id: int = Field(gt=0)


async def _parse(params: dict, caller: str) -> dict:
    def parse_file(file_id, _file, full_path, ext):
        try:
            return parse_code_file(file_id, full_path, ext)
        except CodeParseError as exc:
            raise ValidationError(str(exc)) from exc

    try:
        return await run_uploaded_file_capability(params, caller, SUPPORTED_EXTS, parse_file)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "code-generic-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "code-generic-parser", "parse", _parse,
    description="Parse generic source files into coarse code blocks",
    brief="解析通用代码",
    parameters={"file_id": {"type": "int", "description": "File ID in file storage"}},
    min_role="viewer",
    execution_contract={"side_effect_level": "none", "resource_class": "local_cpu", "timeout_seconds": 120, "parallel_safe": True},
)
