import csv
import io
import logging
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFound
from app.services.file_service import check_file_access, check_file_write_access

logger = logging.getLogger(__name__)


class CsvEditorService:

    async def read(self, db: AsyncSession, file_id: int, user_id: int) -> dict:
        file = await check_file_access(db, file_id, user_id)
        storage_root = Path(get_settings().UPLOAD_DIR).resolve()
        full_path = (storage_root / file.storage_path).resolve()
        if os.path.commonpath([str(storage_root), str(full_path)]) != str(storage_root):
            raise NotFound("文件物理路径不存在")

        if not full_path.exists():
            raise NotFound("文件物理路径不存在")

        delimiter = self._detect_delimiter(full_path)

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        mtime = os.path.getmtime(full_path)

        return {
            "content": content,
            "delimiter": delimiter,
            "mtime": str(mtime),
        }

    async def save(
        self,
        db: AsyncSession,
        file_id: int,
        content: str,
        user_id: int,
        delimiter: str = ",",
        client_mtime: str | None = None,
    ) -> None:
        file = await check_file_write_access(db, file_id, user_id)
        storage_root = Path(get_settings().UPLOAD_DIR).resolve()
        full_path = (storage_root / file.storage_path).resolve()
        if os.path.commonpath([str(storage_root), str(full_path)]) != str(storage_root):
            raise NotFound("文件物理路径不存在")

        if client_mtime and full_path.exists():
            current_mtime = str(os.path.getmtime(full_path))
            if current_mtime != client_mtime:
                raise ValueError("文件已被其他用户修改，请刷新后重试")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

    def _detect_delimiter(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            sample = f.read(4096)
        if sample.count("\t") > sample.count(","):
            return "\t"
        return ","

    async def parse_to_json(self, db: AsyncSession, file_id: int, user_id: int) -> list[dict]:
        data = await self.read(db, file_id, user_id)
        reader = csv.DictReader(io.StringIO(data["content"]), delimiter=data["delimiter"])
        return list(reader)
