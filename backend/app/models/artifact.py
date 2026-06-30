"""Artifact lifecycle models.

framework_artifacts — unified product records (draft / file-backed / hybrid)
framework_artifact_versions — content snapshots at version boundaries
framework_artifact_operations — granular user-level operation history
"""
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Artifact(Base):
    __tablename__ = "framework_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="Owner user id")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="Artifact name (without extension)")
    extension: Mapped[str] = mapped_column(String(32), default="", comment="File extension")
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    kind: Mapped[str] = mapped_column(
        String(32), default="document",
        comment="document / spreadsheet / presentation / image / video / audio / binary / draft"
    )
    storage_mode: Mapped[str] = mapped_column(
        String(16), default="file",
        comment="db (content_json) / file (file_id) / hybrid (both)"
    )
    file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("framework_file_items.id", ondelete="SET NULL"),
        nullable=True, comment="Linked physical file record"
    )
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Structured content for db-mode artifacts")
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Plain text preview")
    binary_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="SHA-256 of latest content")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active / deleted / archived")
    source_module: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Creating module key")
    source_object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Current active version id")
    folder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("framework_file_folders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_artifact_owner", "owner_id", "status"),
        Index("idx_artifact_file", "file_id"),
    )


class ArtifactVersion(Base):
    __tablename__ = "framework_artifact_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("framework_artifacts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="Monotonic version number")
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Full state snapshot")
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Physical file id at this version")
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    binary_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    operation_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ArtifactOperation(Base):
    __tablename__ = "framework_artifact_operations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("framework_artifacts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(
        String(32), default="generic",
        comment="workbook / sheet / document / generic"
    )
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="create / update_cell / replace_range / append_rows / rename / import / export / delete / restore"
    )
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Forward operation payload")
    inverse_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Inverse for undo")
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Pre-op snapshot for restore")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
