"""FileAsset model — tracks file lifecycle states as Agent assets.

Asset types:
- draft:       Working set, not yet ready for publication
- published:   Finalized and visible on the desktop
- evidence:    Knowledge retrieval evidence (provenance-tracked)
- generated:   Agent-generated output (docx, xlsx, image, etc.)
- handoff:     File passed to another module/user/workflow
"""
from datetime import datetime
from sqlalchemy import Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class FileAsset(Base, TimestampMixin):
    """Tracks the lifecycle state of a file within the Agent asset system."""
    __tablename__ = "framework_file_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("framework_file_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("framework_user_accounts.id"),
        nullable=False, index=True,
    )
    asset_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft",
    )
    publish_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft",
    )
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True,
    )
    tool_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
    )
    tool_call_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    source_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("framework_file_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    provenance: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
