from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import AppException, ConflictError, ValidationError
from app.database import get_db
from app.schemas.common import ApiResponse
from app.middleware.auth import require_permission
from app.models.user import User
from app.services.office.text_editor_service import TextEditorService
from app.services.office.csv_editor_service import CsvEditorService

router = APIRouter(prefix="/api/editors", tags=["editors"])

text_svc = TextEditorService()
csv_svc = CsvEditorService()


@router.get("/text/{file_id}")
async def read_text(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    try:
        result = await text_svc.read(db, file_id)
        return ApiResponse(data=result)
    except AppException:
        raise
    except ValueError as e:
        raise ValidationError(str(e))
    except RuntimeError as e:
        raise ConflictError(str(e))


@router.post("/text/{file_id}")
async def save_text(
    file_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    try:
        await text_svc.save(db, file_id, body.get("content", ""), body.get("mtime"))
        return ApiResponse(data={"message": "保存成功"})
    except AppException:
        raise
    except ValueError as e:
        raise ValidationError(str(e))
    except RuntimeError as e:
        raise ConflictError(str(e))


@router.get("/csv/{file_id}")
async def read_csv(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    try:
        result = await csv_svc.read(db, file_id)
        return ApiResponse(data=result)
    except AppException:
        raise
    except ValueError as e:
        raise ValidationError(str(e))
    except RuntimeError as e:
        raise ConflictError(str(e))


@router.post("/csv/{file_id}")
async def save_csv(
    file_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    try:
        await csv_svc.save(db, file_id, body.get("content", ""), body.get("delimiter", ","), body.get("mtime"))
        return ApiResponse(data={"message": "保存成功"})
    except AppException:
        raise
    except ValueError as e:
        raise ValidationError(str(e))
    except RuntimeError as e:
        raise ConflictError(str(e))
