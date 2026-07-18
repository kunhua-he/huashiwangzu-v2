from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FileItemTag(Base, TimestampMixin):
    """Per-user Finder tags on files/folders (multi-tenant)."""

    __tablename__ = "framework_file_item_tags"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "item_type",
            "item_id",
            "tag",
            name="ux_framework_file_item_tags_owner_item_tag",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="User who owns this tag mapping")
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="file | folder")
    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="framework_file_items.id or framework_file_folders.id")
    tag: Mapped[str] = mapped_column(String(32), nullable=False, comment="Tag key: red/orange/yellow/green/blue/purple/gray")

    def __repr__(self) -> str:
        return f"<FileItemTag owner={self.owner_id} {self.item_type}:{self.item_id} tag={self.tag}>"
