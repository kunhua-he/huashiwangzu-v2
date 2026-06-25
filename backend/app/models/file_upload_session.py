from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class FileUploadSession(Base, TimestampMixin):
    __tablename__ = "framework_file_upload_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True, comment="UUID session identifier")
    filename: Mapped[str] = mapped_column(String(512), nullable=False, comment="Original filename")
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, comment="Total expected chunks")
    received_chunks: Mapped[int] = mapped_column(Integer, default=0, comment="Received chunk count (tracked via bitmap on disk)")
    md5_expected: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="Pre-computed MD5 from client")
    status: Mapped[str] = mapped_column(String(32), default="pending", comment="pending / uploading / completed / failed")
    temp_dir: Mapped[str] = mapped_column(String(1024), nullable=False, comment="Chunk storage directory")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Auto-cleanup deadline (24h)")
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Creator user id")
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="Soft delete flag")

    def __repr__(self) -> str:
        return f"<FileUploadSession session_id={self.session_id} filename={self.filename} status={self.status}>"
