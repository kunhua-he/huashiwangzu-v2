import csv

from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_reader import decode_text_bytes
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/csv-parser", tags=["csv-parser"])


class ParseRequest(BaseModel):
    file_id: int


def _detect_delimiter(head: str) -> str:
    if "\t" in head:
        return "\t"
    if ";" in head:
        return ";"
    return ","


async def _parse(params: dict, caller: str) -> dict:
    allowed = {"csv", "tsv"}

    def parse_file(file_id, _file, full_path, ext):
        content = decode_text_bytes(full_path.read_bytes())

        blocks = []
        lines = content.strip().splitlines()
        if not lines:
            return {"file_id": file_id, "format": ext, "blocks": [], "resources": []}

        delimiter = _detect_delimiter(lines[0])
        reader = csv.reader(lines, delimiter=delimiter)

        rows = list(reader)
        if not rows:
            return {"file_id": file_id, "format": ext, "blocks": [], "resources": []}

        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []

        # Summary block
        summary = f"表格：{len(headers)}列 x {len(data_rows)}行数据"
        if headers:
            summary += f"\n表头：{' | '.join(headers)}"
        blocks.append({"type": "段落", "text": summary, "page": None, "resource_ref": None})

        # Header block
        if headers:
            blocks.append({"type": "表格", "text": " | ".join(headers), "page": None, "resource_ref": None})

        # Data blocks - batch in groups of 50 rows
        batch_size = 50
        for start in range(0, len(data_rows), batch_size):
            batch = data_rows[start:start + batch_size]
            row_texts = []
            for i, row in enumerate(batch):
                line_num = start + i + 2
                cols = " | ".join(row)
                row_texts.append(f"行{line_num}：{cols}")
            block_text = "\n".join(row_texts)
            blocks.append({"type": "表格", "text": block_text, "page": None, "resource_ref": None})

        return {
            "file_id": file_id,
            "format": ext,
            "blocks": blocks,
            "resources": [],
        }

    return await run_uploaded_file_capability(params, caller, allowed, parse_file)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "csv-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "csv-parser", "parse", _parse,
    description="Parse CSV/TSV files into unified content blocks",
    brief="解析 CSV/TSV 表格文件",
    parameters={"file_id": {"type": "int", "description": "File ID in file storage"}},
    min_role="viewer",
)
