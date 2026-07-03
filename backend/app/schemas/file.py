from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileResponse(BaseModel):
    id: int
    name: str
    extension: str
    size: int
    folder_id: Optional[int] = None
    mime_type: str
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        return f"{self.name}.{self.extension}" if self.extension else self.name

    model_config = {"from_attributes": True}


class FileListItem(BaseModel):
    id: int
    name: str
    extension: Optional[str] = None
    size: int
    parent_id: Optional[int] = None
    created_at: Optional[datetime] = None
    is_folder: bool
    mime_type: Optional[str] = None
    storage_path: Optional[str] = None


class FileListResponse(BaseModel):
    items: list[FileListItem]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    id: int
    name: str
    extension: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    exists: bool = False
    deduplicated: bool = False


class UploadSessionCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    total_chunks: int = Field(..., ge=1, le=10000)
    md5_expected: Optional[str] = Field(None, max_length=32)
    expires_in_hours: int = Field(24, ge=1, le=168)


class UploadSessionResponse(BaseModel):
    session_id: str
    filename: str
    total_chunks: int
    received_chunks: int
    status: str
    expires_at: datetime


class UploadSessionCompleteRequest(BaseModel):
    folder_id: Optional[int] = None
    relative_path: str = ""


class UploadSessionCompleteResponse(BaseModel):
    session: UploadSessionResponse
    file: UploadResponse


class PreviewResponse(BaseModel):
    content: Optional[str] = None
    format: Optional[str] = None
    file_info: dict
    mime_type: Optional[str] = None
    download_url: Optional[str] = None


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[int] = None


class RenameRequest(BaseModel):
    type: str  # "file" or "folder"
    id: int
    new_name: str


class MoveRequest(BaseModel):
    type: str
    id: int
    target_folder_id: Optional[int] = None


class DeleteRequest(BaseModel):
    type: str  # "file" or "folder"
    id: int


class SearchRequest(BaseModel):
    keyword: str = ""
    extension: Optional[str] = None
    page: int = 1
    page_size: int = 50
