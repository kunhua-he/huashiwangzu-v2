import csv
import io
from pathlib import Path
from typing import Any

from app.core.exceptions import ValidationError
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_reader import decode_text_bytes
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/csv-parser", tags=["csv-parser"])

MAX_EMITTED_DATA_ROWS = 1000
DATA_BLOCK_BATCH_SIZE = 50
MAX_CELL_CHARS = 500
SNIFFER_SAMPLE_CHARS = 8192
SCHEMA_VERSION = "content-ir/v1"
SOURCE_MODULE = "csv-parser"
PARSER_NAME = "csv-parser:parse"


class ParseRequest(BaseModel):
    file_id: int


def _coerce_file_id(params: dict) -> int:
    try:
        file_id = int(params.get("file_id", 0))
    except (TypeError, ValueError):
        raise ValidationError("file_id must be a positive integer")
    if file_id <= 0:
        raise ValidationError("file_id must be a positive integer")
    return file_id


def _delimiter_label(delimiter: str) -> str:
    if delimiter == "\t":
        return "tab"
    if delimiter == ";":
        return "semicolon"
    if delimiter == "|":
        return "pipe"
    return ","


def _detect_delimiter(sample: str, ext: str) -> str:
    if ext == "tsv":
        return "\t"

    candidate_lines = [line for line in sample.splitlines() if line.strip()]
    if not candidate_lines:
        return ","
    probe = "\n".join(candidate_lines[:20])
    try:
        dialect = csv.Sniffer().sniff(probe, delimiters=",\t;|")
        if dialect.delimiter in {",", "\t", ";", "|"}:
            return dialect.delimiter
    except csv.Error:
        pass

    counts = {
        delimiter: sum(line.count(delimiter) for line in candidate_lines[:20])
        for delimiter in (",", "\t", ";", "|")
    }
    delimiter, count = max(counts.items(), key=lambda item: item[1])
    return delimiter if count > 0 else ","


def _source(file_id: int, ext: str) -> dict[str, object]:
    mime_type = "text/tab-separated-values" if ext == "tsv" else "text/csv"
    return {
        "module": SOURCE_MODULE,
        "file_id": file_id,
        "filename": None,
        "mime_type": mime_type,
        "format": ext,
    }


def _block(
    block_type: str,
    text: str,
    source_ref: dict[str, object],
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    data: dict[str, object] = {"source_ref": source_ref}
    if metadata:
        data.update(metadata)
    return {
        "type": block_type,
        "text": text,
        "page": None,
        "resource_ref": None,
        "source_ref": source_ref,
        "data": data,
    }


def _sheet_block(
    sheet_name: str,
    source_ref: dict[str, object],
    children: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "type": "sheet",
        "text": sheet_name,
        "page": None,
        "resource_ref": None,
        "source_ref": source_ref,
        "children": children,
        "data": {"source_ref": source_ref, "sheet_name": sheet_name},
    }


def _base_result(
    file_id: int,
    ext: str,
    blocks: list[dict[str, object]],
    warnings: list[dict[str, object]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "content_type": "spreadsheet",
        "title": f"{ext.upper()} table",
        "source_file_id": file_id if file_id > 0 else None,
        "source_module": SOURCE_MODULE,
        "parser": PARSER_NAME,
        "source": _source(file_id, ext),
        "file_id": file_id,
        "format": ext,
        "blocks": blocks,
        "resources": [],
        "warnings": warnings or [],
        "metadata": {
            "parser": PARSER_NAME,
            "format": ext,
            **(metadata or {}),
        },
        "quality": {},
    }


def _trim_cell(cell: str) -> str:
    normalized = cell.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= MAX_CELL_CHARS:
        return normalized
    return f"{normalized[:MAX_CELL_CHARS]}..."


def _format_row(line_num: int, row: list[str]) -> str:
    return f"行{line_num}：" + " | ".join(_trim_cell(cell) for cell in row)


def _column_label(index: int) -> str:
    label = ""
    current = max(index, 1)
    while current:
        current, remainder = divmod(current - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def _range_for_table(row_count: int, column_count: int) -> str | None:
    if row_count <= 0 or column_count <= 0:
        return None
    return f"A1:{_column_label(column_count)}{row_count}"


def _normalize_row_length(row: list[str], column_count: int) -> list[str]:
    trimmed = [_trim_cell(cell) for cell in row]
    if len(trimmed) < column_count:
        return [*trimmed, *([""] * (column_count - len(trimmed)))]
    return trimmed[:column_count]


def parse_csv_content(content: str, file_id: int, ext: str) -> dict[str, object]:
    content = content.lstrip("\ufeff")
    if not content.strip():
        source_ref = {
            "format": ext,
            "line_start": None,
            "line_end": None,
            "row_count": 0,
            "kind": "empty_file",
        }
        table = _block(
            "table",
            "空CSV/TSV文件：0列 x 0行数据",
            source_ref,
            {"headers": [], "rows": [], "start_cell": "A1", "range": None},
        )
        return _base_result(
            file_id,
            ext,
            [_sheet_block(ext, source_ref, [table])],
            warnings=[{"code": "empty_file", "message": "CSV/TSV file is empty"}],
            metadata={"row_count": 0, "header_count": 0, "truncated": False},
        )

    delimiter = _detect_delimiter(content[:SNIFFER_SAMPLE_CHARS], ext)
    reader = csv.reader(io.StringIO(content), delimiter=delimiter, strict=True)

    headers: list[str] = []
    data_row_count = 0
    emitted_row_count = 0
    emitted_rows: list[list[str]] = []
    last_physical_line = 0

    try:
        for physical_line, row in enumerate(reader, start=1):
            last_physical_line = physical_line
            if physical_line == 1:
                headers = [_trim_cell(cell) for cell in row]
                continue

            data_row_count += 1
            if emitted_row_count >= MAX_EMITTED_DATA_ROWS:
                continue

            emitted_row_count += 1
            emitted_rows.append([_trim_cell(cell) for cell in row])
    except csv.Error as exc:
        raise ValidationError(f"Invalid CSV content: {exc}")

    summary = f"表格：{len(headers)}列 x {data_row_count}行数据"
    summary += f"\n分隔符：{_delimiter_label(delimiter)}"
    if headers:
        summary += f"\n表头：{' | '.join(_trim_cell(header) for header in headers)}"
    if data_row_count > emitted_row_count:
        omitted = data_row_count - emitted_row_count
        summary += f"\n仅输出前 {emitted_row_count} 行，剩余 {omitted} 行已省略。"

    warnings: list[dict[str, object]] = []
    if data_row_count > emitted_row_count:
        warnings.append({
            "code": "row_limit_reached",
            "message": f"Only first {emitted_row_count} rows emitted",
            "omitted_rows": data_row_count - emitted_row_count,
        })

    summary_ref = {
        "format": ext,
        "line_start": 1,
        "line_end": last_physical_line or 1,
        "row_count": data_row_count,
        "row_start": 1,
        "row_end": last_physical_line or 1,
        "range": _range_for_table(1 + emitted_row_count if headers else emitted_row_count, len(headers)),
        "kind": "table",
    }
    column_count = len(headers) or max((len(row) for row in emitted_rows), default=0)
    normalized_headers = headers or [f"column_{index}" for index in range(1, column_count + 1)]
    normalized_rows = [_normalize_row_length(row, column_count) for row in emitted_rows]
    text_lines = [summary]
    if normalized_headers:
        text_lines.append("表头：" + " | ".join(normalized_headers))
    text_lines.extend(
        _format_row(index + 2, row)
        for index, row in enumerate(normalized_rows)
    )
    table = _block(
        "table",
        "\n".join(text_lines),
        summary_ref,
        {
            "headers": normalized_headers,
            "rows": normalized_rows,
            "start_cell": "A1",
            "range": summary_ref["range"],
            "delimiter": delimiter,
        },
    )
    blocks = [_sheet_block(ext, summary_ref, [table])]

    return _base_result(
        file_id,
        ext,
        blocks,
        warnings=warnings,
        metadata={
            "delimiter": delimiter,
            "delimiter_label": _delimiter_label(delimiter),
            "header_count": len(headers),
            "row_count": data_row_count,
            "rows_emitted": emitted_row_count,
            "truncated": data_row_count > emitted_row_count,
        },
    )


def parse_csv_path(file_id: int, full_path: Path, ext: str) -> dict[str, object]:
    content = decode_text_bytes(full_path.read_bytes())
    return parse_csv_content(content, file_id, ext)


async def _parse(params: dict, caller: str) -> dict:
    allowed = {"csv", "tsv"}
    file_id = _coerce_file_id(params)

    def parse_file(file_id: int, _file: object, full_path: Path, ext: str) -> dict[str, object]:
        return parse_csv_path(file_id, full_path, ext)

    return await run_uploaded_file_capability({"file_id": file_id}, caller, allowed, parse_file)


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
