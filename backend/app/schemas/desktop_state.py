from pydantic import BaseModel


class DesktopStateResponse(BaseModel):
    user_id: int
    state_json: dict = {}
    version: int = 1


class DesktopStateSaveRequest(BaseModel):
    state_json: dict


class DesktopAuditLogRequest(BaseModel):
    action: str = ""
    params: dict = {}
    target_app: str = ""
