"""Source-file lifecycle helpers for the knowledge pipeline."""
from dataclasses import dataclass

from app.models.file import File
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class SourceFileAvailability:
    available: bool
    reason: str = ""


class SourceFileUnavailable(Exception):
    """Raised when a source file was intentionally removed from the active file tree."""

    def __init__(self, file_id: int, reason: str):
        self.file_id = file_id
        self.reason = reason
        super().__init__(f"Source file {file_id} unavailable: {reason}")


async def get_source_file_availability(
    db: AsyncSession,
    file_id: int,
) -> SourceFileAvailability:
    """Classify lifecycle absence without reading file contents from disk."""
    file = await db.get(File, file_id)
    if not file:
        return SourceFileAvailability(False, "source_file_missing")
    if file.deleted:
        return SourceFileAvailability(False, "source_file_deleted")
    return SourceFileAvailability(True, "")


async def raise_if_source_unavailable(db: AsyncSession, file_id: int) -> None:
    state = await get_source_file_availability(db, file_id)
    if not state.available:
        raise SourceFileUnavailable(file_id, state.reason)
