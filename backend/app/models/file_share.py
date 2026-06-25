from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.models.base import Base, TimestampMixin


class FileShare(Base, TimestampMixin):
    __tablename__ = "framework_file_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("framework_file_items.id"), nullable=False)
    shared_by_owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("framework_user_accounts.id"), nullable=False)
    shared_with_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("framework_user_accounts.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), default="read", comment="read | edit | comment")
    scope: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="Scope of share: e.g. {\"types\": [\"file\", \"document_ir\", \"artifact\", \"evidence\"]}")
    expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="Share expiry time")
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="Reason for sharing")
    publish: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="Allow publish")
    reshare: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="Allow reshare")

    def __repr__(self) -> str:
        return f"<FileShare id={self.id} file_id={self.file_id}>"
