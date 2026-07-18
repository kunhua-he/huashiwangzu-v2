"""DOC 解析器：把老二进制 .doc 转成统一 content-ir/v1 blocks。

支持格式：.doc
解析策略：macOS textutil 优先（textutil -convert txt），失败再尝试 LibreOffice 转 txt。
切块规则：按空行切段落；首段非空视为 heading。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

SCHEMA_VERSION = "content-ir/v1"
SUPPORTED_EXTS = {"doc"}
MAX_TEXT_BYTES = 2 * 1024 * 1024
MODULE_KEY = "doc-parser"


class DocParseError(ValueError):
    """DOC 解析失败。"""


def _source_ref(file_id: int, line_start: int | None, line_end: int | None = None, section: str = "body") -> dict[str, object]:
    return {
        "file_id": file_id,
        "format": "doc",
        "section": section,
        "line_start": line_start,
        "line_end": line_end if line_end is not None else line_start,
        "module": MODULE_KEY,
    }


def _block(block_type: str, text: str, source_ref: dict[str, object]) -> dict[str, object]:
    return {
        "type": block_type,
        "text": text,
        "page": None,
        "resource_ref": None,
        "source_ref": source_ref,
    }


def _run_textutil(path: Path, out_dir: Path) -> str:
    textutil = shutil.which("textutil")
    if not textutil:
        raise DocParseError("macOS textutil 不可用，无法解析 .doc")
    out_path = out_dir / f"{path.stem}.txt"
    proc = subprocess.run(
        [textutil, "-convert", "txt", "-output", str(out_path), str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size <= 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DocParseError(f"textutil 转文本失败: {detail or 'empty output'}")
    return out_path.read_text(encoding="utf-8", errors="replace")


def _run_libreoffice_txt(path: Path, out_dir: Path) -> str:
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    soffice = next((c for c in candidates if c and Path(c).exists()), None)
    if not soffice:
        raise DocParseError("LibreOffice 不可用，无法兜底解析 .doc")
    proc = subprocess.run(
        [soffice, "--headless", "--convert-to", "txt:Text", "--outdir", str(out_dir), str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    out_path = out_dir / f"{path.stem}.txt"
    if proc.returncode != 0 or not out_path.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DocParseError(f"LibreOffice 转文本失败: {detail or 'empty output'}")
    return out_path.read_text(encoding="utf-8", errors="replace")


def 抽取doc文本(path: Path) -> tuple[str, str]:
    """返回 (文本, 提取方式)。"""
    with tempfile.TemporaryDirectory(prefix="doc_parser_") as tmp:
        tmp_dir = Path(tmp)
        try:
            return _run_textutil(path, tmp_dir), "textutil"
        except (DocParseError, subprocess.TimeoutExpired, OSError) as first_error:
            try:
                return _run_libreoffice_txt(path, tmp_dir), "libreoffice"
            except (DocParseError, subprocess.TimeoutExpired, OSError) as second_error:
                raise DocParseError(
                    f"DOC 文本提取失败: textutil={first_error}; libreoffice={second_error}"
                ) from second_error


def 切成段落块(file_id: int, text: str) -> list[dict[str, object]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text.encode("utf-8", errors="ignore")) > MAX_TEXT_BYTES:
        text = text.encode("utf-8", errors="ignore")[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
    lines = text.splitlines()
    blocks: list[dict[str, object]] = []
    buf: list[str] = []
    start: int | None = None
    for idx, line in enumerate(lines, start=1):
        if line.strip() == "":
            if buf:
                body = "\n".join(buf).strip()
                if body:
                    kind = "heading" if not blocks else "paragraph"
                    blocks.append(_block(kind, body, _source_ref(file_id, start, idx - 1, kind)))
                buf = []
                start = None
            continue
        if start is None:
            start = idx
        buf.append(line)
    if buf:
        body = "\n".join(buf).strip()
        if body:
            kind = "heading" if not blocks else "paragraph"
            blocks.append(_block(kind, body, _source_ref(file_id, start, len(lines), kind)))
    if not blocks:
        blocks.append(_block(
            "paragraph",
            "(empty doc file)",
            {**_source_ref(file_id, None, None, "body"), "empty": True},
        ))
    return blocks


def parse_doc_file(file_id: int, path: Path | str, ext: str = "doc") -> dict[str, object]:
    normalized = ext.lower().lstrip(".")
    if normalized not in SUPPORTED_EXTS:
        raise DocParseError(f"Unsupported format '{normalized}'")
    full_path = Path(path)
    if not full_path.exists():
        raise DocParseError(f"File not found: {full_path}")
    text, method = 抽取doc文本(full_path)
    blocks = 切成段落块(file_id, text)
    return {
        "schema_version": SCHEMA_VERSION,
        "content_type": "document",
        "title": full_path.name,
        "source_file_id": file_id,
        "source_module": MODULE_KEY,
        "parser": MODULE_KEY,
        "source": {
            "module": MODULE_KEY,
            "file_id": file_id,
            "filename": full_path.name,
            "mime_type": "application/msword",
            "format": "doc",
        },
        "file_id": file_id,
        "format": "doc",
        "blocks": blocks,
        "resources": [],
        "metadata": {
            "parser": MODULE_KEY,
            "format": "doc",
            "filename": full_path.name,
            "extract_method": method,
            "paragraph_count": len(blocks),
        },
        "warnings": [f"extracted_via_{method}"],
    }
