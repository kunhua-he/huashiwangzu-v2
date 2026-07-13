from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.exceptions import ValidationError
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import (
    authorized_capability_snapshot,
    call_capability_for_user,
    semantic_failure_reason,
)

router = APIRouter(prefix="/api/modules", tags=["modules"])


class ModuleCallRequest(BaseModel):
    target_module: str
    action: str
    parameters: dict = {}


@router.post("/call")
async def module_call(payload: ModuleCallRequest, user: User = Depends(require_permission("viewer"))):
    result = await call_capability_for_user(
        payload.target_module,
        payload.action,
        payload.parameters,
        user=user,
    )
    failure_reason = semantic_failure_reason(result)
    if failure_reason:
        raise ValidationError(str(failure_reason or f"{payload.target_module}:{payload.action} failed"))
    return ApiResponse(data=result)


@router.get("/capabilities")
async def capabilities(user: User = Depends(require_permission("viewer"))):
    snapshot = await authorized_capability_snapshot(user_id=user.id)
    return ApiResponse(data=snapshot["capabilities"])
