from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_reader import decode_text_bytes
from app.services.module_registry import register_capability
from app.services.uploaded_file_runner import run_uploaded_file_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/text-parser", tags=["text-parser"])


class ParseRequest(BaseModel):
    file_id: int


async def _parse(params: dict, caller: str) -> dict:
    allowed = {"txt", "md", "markdown", "text", "log"}

    def parse_file(file_id, _file, full_path, ext):
        content = decode_text_bytes(full_path.read_bytes())

        content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = content.splitlines(keepends=False)
        blocks = []
        is_md = ext in ("md", "markdown")

        if is_md:
            para_lines = []
            in_code_block = False
            for line in lines:
                if line.startswith("```"):
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    in_code_block = not in_code_block
                    blocks.append({"type": "段落", "text": line, "page": None, "resource_ref": None})
                    continue
                if in_code_block:
                    blocks.append({"type": "段落", "text": line, "page": None, "resource_ref": None})
                    continue
                if line.startswith("#"):
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    title_text = line.lstrip("#").strip()
                    blocks.append({"type": "标题", "text": title_text, "page": None, "resource_ref": None})
                    continue
                if line.strip() == "":
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    continue
                para_lines.append(line)
            if para_lines:
                text = "\n".join(para_lines).strip()
                if text:
                    blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})
        else:
            para_lines = []
            for line in lines:
                if line.strip() == "":
                    if para_lines:
                        text = "\n".join(para_lines).strip()
                        if text:
                            blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})
                        para_lines = []
                    continue
                para_lines.append(line)
            if para_lines:
                text = "\n".join(para_lines).strip()
                if text:
                    blocks.append({"type": "段落", "text": text, "page": None, "resource_ref": None})

        return {
            "file_id": file_id,
            "format": ext,
            "blocks": blocks,
            "resources": [],
        }

    return await run_uploaded_file_capability(params, caller, allowed, parse_file)


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "text-parser", "status": "ok"})


@router.post("/parse")
async def call_parse(payload: ParseRequest, user: User = Depends(require_permission("viewer"))):
    result = await _parse({"file_id": payload.file_id}, f"user:{user.id}")
    return ApiResponse(data=result)


register_capability(
    "text-parser", "parse", _parse,
    description="Parse TXT/MD files into unified content blocks",
    brief="解析文本文件",
    parameters={"file_id": {"type": "int"}},
    min_role="viewer",
)
