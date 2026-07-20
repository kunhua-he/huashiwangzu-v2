"""本解析器：解析 HTML/HTM，按标题/可见文本/script/style 切成统一 content-ir blocks。

支持格式：.htm, .html
切块规则文件：同模块目录 `切块规则.json`
"""
from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from pathlib import Path

SCHEMA_VERSION = "content-ir/v1"
MODULE_KEY = "code-html-parser"
SUPPORTED_EXTS = {'html', 'htm'}
RULES_PATH = Path(__file__).resolve().parents[1] / "切块规则.json"
MAX_TEXT_BYTES_DEFAULT = 1024 * 1024


class CodeParseError(ValueError):
    """代码文件解析失败。"""


_RULES_CACHE: dict | None = None
_RULES_MTIME: float | None = None


def 加载切块规则(force: bool = False) -> dict:
    """读切块规则；默认按 mtime 缓存，force=True 强制重载。"""
    global _RULES_CACHE, _RULES_MTIME
    if not RULES_PATH.exists():
        raise CodeParseError(f"缺少切块规则: {RULES_PATH}")
    mtime = RULES_PATH.stat().st_mtime
    if (
        not force
        and _RULES_CACHE is not None
        and _RULES_MTIME is not None
        and mtime == _RULES_MTIME
    ):
        return _RULES_CACHE
    try:
        data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # 坏文件不覆盖已有好缓存
        if _RULES_CACHE is not None and not force:
            return _RULES_CACHE
        raise CodeParseError(f"切块规则 JSON 无效: {exc}") from exc
    if not isinstance(data, dict):
        raise CodeParseError("切块规则必须是 JSON 对象")
    _RULES_CACHE = data
    _RULES_MTIME = mtime
    return data


def 重载切块规则() -> dict:
    """显式热加载：强制读盘并返回规则摘要（供 reload_rules capability）。"""
    rules = 加载切块规则(force=True)
    unit_patterns = rules.get("unit_patterns") or []
    return {
        "ok": True,
        "module": MODULE_KEY,
        "rules_path": str(RULES_PATH),
        "rules_name": RULES_PATH.name,
        "mtime": _RULES_MTIME,
        "language": rules.get("language"),
        "split_mode": rules.get("split_mode"),
        "extensions": rules.get("extensions") or sorted(SUPPORTED_EXTS),
        "unit_patterns_count": len(unit_patterns) if isinstance(unit_patterns, list) else 0,
        "max_bytes": int(rules.get("max_bytes", MAX_TEXT_BYTES_DEFAULT)),
    }


def 解码文本(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "gb2312"):
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1"), "latin-1"


def 读文件样本(path: Path, max_bytes: int) -> tuple[bytes, dict[str, object]]:
    size = path.stat().st_size
    with path.open("rb") as fh:
        raw = fh.read(max_bytes + 4 if size > max_bytes else max_bytes)
    return raw, {
        "original_size": size,
        "parsed_bytes": len(raw),
        "max_bytes": max_bytes,
        "truncated": size > len(raw),
    }


def _source_ref(file_id: int, file_format: str, line_start: int | None, line_end: int | None = None, section: str = "body") -> dict[str, object]:
    return {
        "file_id": file_id,
        "format": file_format,
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


def _line_count_up_to(text: str, index: int) -> int:
    if index <= 0:
        return 1
    return text.count("\n", 0, index) + 1


def 切python(content: str, file_id: int, file_format: str, rules: dict) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 切正则(content, file_id, file_format, rules)

    # 模块 docstring → heading
    module_doc = ast.get_docstring(tree)
    if module_doc and rules.get("module_docstring_as_heading", True):
        end_line = 1
        if tree.body:
            first = tree.body[0]
            end_line = getattr(first, "end_lineno", getattr(first, "lineno", 1)) or 1
        blocks.append(_block("heading", module_doc.strip(), _source_ref(file_id, file_format, 1, end_line, "heading")))

    lines = content.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = getattr(node, "lineno", 1) or 1
            end = getattr(node, "end_lineno", start) or start
            # 尽量包含装饰器
            if getattr(node, "decorator_list", None):
                start = min(start, min(d.lineno for d in node.decorator_list if getattr(d, "lineno", None)))
            snippet = "\n".join(lines[start - 1:end])
            if snippet.strip():
                blocks.append(_block("code", snippet, _source_ref(file_id, file_format, start, end, "code")))
            doc = ast.get_docstring(node)
            if doc and rules.get("emit_docstring_paragraph", True):
                blocks.append(_block("paragraph", doc.strip(), _source_ref(file_id, file_format, start, end, "docstring")))
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            # 已作为模块 docstring 处理
            continue
        elif isinstance(node, ast.Assign) or isinstance(node, ast.AnnAssign) or isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            start = getattr(node, "lineno", 1) or 1
            end = getattr(node, "end_lineno", start) or start
            snippet = "\n".join(lines[start - 1:end])
            if snippet.strip():
                # 顶层 import/常量并入 code
                blocks.append(_block("code", snippet, _source_ref(file_id, file_format, start, end, "toplevel")))

    if not blocks:
        return 切正则(content, file_id, file_format, rules)
    return _合并相邻code(blocks)


def _合并相邻code(blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    if not blocks:
        return blocks
    merged: list[dict[str, object]] = []
    for block in blocks:
        if (
            merged
            and block["type"] == "code"
            and merged[-1]["type"] == "code"
            and merged[-1]["source_ref"].get("section") == "toplevel"
            and block["source_ref"].get("section") == "toplevel"
        ):
            prev = merged[-1]
            prev["text"] = f"{prev['text']}\\n{block['text']}"
            prev_ref = dict(prev["source_ref"])
            prev_ref["line_end"] = block["source_ref"].get("line_end")
            prev["source_ref"] = prev_ref
            continue
        merged.append(block)
    return merged


def 切正则(content: str, file_id: int, file_format: str, rules: dict) -> list[dict[str, object]]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    unit_patterns = [re.compile(p) for p in rules.get("unit_patterns", [])]
    line_comments = tuple(rules.get("line_comment", []))
    block_comments = rules.get("block_comment", [])
    preserve_indent = bool(rules.get("preserve_indent", True))
    indent_based = bool(rules.get("indent_based_body", False))
    brace_based = bool(rules.get("brace_based_body", False))
    blank_split = bool(rules.get("blank_line_split", False))

    blocks: list[dict[str, object]] = []
    comment_buf: list[str] = []
    comment_start: int | None = None
    i = 0
    n = len(lines)

    def flush_comment(end_line: int) -> None:
        nonlocal comment_buf, comment_start
        if not comment_buf:
            return
        text = "\n".join(comment_buf).strip()
        if text:
            blocks.append(_block("paragraph", text, _source_ref(file_id, file_format, comment_start, end_line, "comment")))
        comment_buf = []
        comment_start = None

    def is_unit_start(line: str) -> bool:
        stripped = line if preserve_indent else line.lstrip()
        return any(p.search(stripped) for p in unit_patterns)

    def line_indent(line: str) -> int:
        return len(line) - len(line.lstrip(" \\t"))

    # 文件头：跳过 shebang / php 开标签，收集前置注释作为 heading
    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("#!") or stripped in {"<?php", "<?", "<?="}:
            i += 1
            continue
        if any(stripped.startswith(c) for c in line_comments):
            if comment_start is None:
                comment_start = i + 1
            comment_buf.append(stripped)
            i += 1
            continue
        matched_bc = False
        for bc in block_comments:
            start_tok = bc.get("start", "")
            end_tok = bc.get("end", "")
            if start_tok and start_tok in lines[i]:
                matched_bc = True
                if comment_start is None:
                    comment_start = i + 1
                comment_buf.append(stripped)
                if end_tok and end_tok in lines[i][lines[i].find(start_tok) + len(start_tok):]:
                    i += 1
                    break
                i += 1
                while i < n:
                    comment_buf.append(lines[i].strip())
                    if end_tok and end_tok in lines[i]:
                        i += 1
                        break
                    i += 1
                break
        if matched_bc:
            continue
        break
    if comment_buf:
        raw_text = "\n".join(x for x in comment_buf if x).strip()
        cleaned = []
        for row in raw_text.splitlines():
            row2 = row.strip()
            for c in line_comments:
                if row2.startswith(c):
                    row2 = row2[len(c):].strip()
                    break
            if row2.startswith("/*") or row2.startswith("/**"):
                row2 = row2.lstrip("/*").strip()
            if row2.endswith("*/"):
                row2 = row2[:-2].strip()
            if row2.startswith("*"):
                row2 = row2[1:].strip()
            if row2:
                cleaned.append(row2)
        text = "\n".join(cleaned).strip() or raw_text
        if text:
            blocks.append(_block("heading", text, _source_ref(file_id, file_format, comment_start, i, "heading")))
        comment_buf = []
        comment_start = None

    in_block_comment = False
    block_end_token = ""
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 块注释
        if not in_block_comment:
            for bc in block_comments:
                start_tok = bc.get("start", "")
                end_tok = bc.get("end", "")
                if start_tok and start_tok in line:
                    in_block_comment = True
                    block_end_token = end_tok
                    if comment_start is None:
                        comment_start = i + 1
                    comment_buf.append(stripped)
                    if end_tok and end_tok in line[line.find(start_tok) + len(start_tok):]:
                        in_block_comment = False
                        flush_comment(i + 1)
                    i += 1
                    break
            else:
                pass
            if in_block_comment and comment_buf and comment_buf[-1] == stripped:
                # 已消费本行
                continue
        else:
            if comment_start is None:
                comment_start = i + 1
            comment_buf.append(stripped)
            if block_end_token and block_end_token in line:
                in_block_comment = False
                flush_comment(i + 1)
            i += 1
            continue

        if any(stripped.startswith(c) for c in line_comments):
            if comment_start is None:
                comment_start = i + 1
            comment_buf.append(stripped)
            i += 1
            continue
        else:
            flush_comment(i)

        if not stripped:
            i += 1
            continue

        if unit_patterns and is_unit_start(line):
            start = i + 1
            end = i
            if indent_based:
                base_indent = line_indent(line)
                j = i + 1
                while j < n:
                    nxt = lines[j]
                    if not nxt.strip():
                        j += 1
                        continue
                    if line_indent(nxt) > base_indent:
                        j += 1
                        continue
                    # 装饰器后的 def 已在 start；同级结束
                    if is_unit_start(nxt) or line_indent(nxt) <= base_indent:
                        break
                    j += 1
                end = j
            elif brace_based:
                depth = line.count("{") - line.count("}")
                j = i + 1
                while j < n and depth > 0:
                    depth += lines[j].count("{") - lines[j].count("}")
                    j += 1
                # 若没有大括号，退化为单行/直到空行
                if depth == 0 and "{" not in line:
                    j = i + 1
                    while j < n and lines[j].strip() and not is_unit_start(lines[j]):
                        j += 1
                end = max(j, i + 1)
            else:
                j = i + 1
                while j < n and lines[j].strip() and not is_unit_start(lines[j]):
                    j += 1
                end = j
            snippet_lines = lines[i:end]
            snippet = "\n".join(snippet_lines)
            if not preserve_indent:
                snippet = "\n".join(x.lstrip() for x in snippet_lines)
            if snippet.strip():
                blocks.append(_block("code", snippet.rstrip(), _source_ref(file_id, file_format, start, end, "code")))
            i = end
            continue

        if blank_split:
            start = i + 1
            j = i
            chunk: list[str] = []
            while j < n and lines[j].strip():
                if unit_patterns and is_unit_start(lines[j]) and chunk:
                    break
                chunk.append(lines[j])
                j += 1
            text = "\n".join(chunk).rstrip()
            if text:
                blocks.append(_block("code", text, _source_ref(file_id, file_format, start, j, "code")))
            i = j
            continue

        # 默认：逐非空行聚合到下一空行
        start = i + 1
        j = i
        chunk = []
        while j < n and lines[j].strip():
            if unit_patterns and is_unit_start(lines[j]) and chunk:
                break
            chunk.append(lines[j])
            j += 1
        text = "\n".join(chunk).rstrip()
        if text:
            blocks.append(_block("code", text, _source_ref(file_id, file_format, start, j, "code")))
        i = j

    flush_comment(n)
    if not blocks:
        body = content.strip() or "(empty code file)"
        blocks.append(_block(
            "code" if content.strip() else "paragraph",
            body,
            {**_source_ref(file_id, file_format, 1 if content.strip() else None, max(n, 1) if content.strip() else None, "body"), **({"empty": True} if not content.strip() else {})},
        ))
    return blocks


class _Html提取器(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks_raw: list[tuple[str, str, int]] = []
        self._capture_tag: str | None = None
        self._buf: list[str] = []
        self._start_line = 1
        self._visible_buf: list[str] = []
        self._visible_start = 1
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._flush_visible()
            self._capture_tag = tag
            self._buf = []
            self._start_line = self.getpos()[0]
            return
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "title"}:
            self._flush_visible()
            self._capture_tag = "heading"
            self._buf = []
            self._start_line = self.getpos()[0]
        elif tag in {"p", "li", "td", "th", "div", "section", "article"}:
            if self._capture_tag is None:
                self._visible_start = self.getpos()[0]

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._capture_tag in {"script", "style"} and tag == self._capture_tag:
            text = "".join(self._buf).strip()
            if text:
                self.blocks_raw.append(("code", text, self._start_line))
            self._capture_tag = None
            self._buf = []
            return
        if self._capture_tag == "heading" and tag in {"h1", "h2", "h3", "h4", "h5", "h6", "title"}:
            text = "".join(self._buf).strip()
            if text:
                self.blocks_raw.append(("heading", text, self._start_line))
            self._capture_tag = None
            self._buf = []
            return
        if tag in {"p", "li", "td", "th", "div", "section", "article"}:
            self._flush_visible()

    def handle_data(self, data: str) -> None:
        if self._capture_tag in {"script", "style", "heading"}:
            self._buf.append(data)
            return
        if data.strip():
            if not self._visible_buf:
                self._visible_start = self.getpos()[0]
            self._visible_buf.append(data)

    def _flush_visible(self) -> None:
        text = "".join(self._visible_buf).strip()
        if text:
            self.blocks_raw.append(("paragraph", re.sub(r"\\s+", " ", text), self._visible_start))
        self._visible_buf = []


def 切html(content: str, file_id: int, file_format: str, rules: dict) -> list[dict[str, object]]:
    parser = _Html提取器()
    try:
        parser.feed(content)
        parser.close()
    except Exception:
        return 切正则(content, file_id, file_format, rules)
    parser._flush_visible()
    blocks: list[dict[str, object]] = []
    for kind, text, start in parser.blocks_raw:
        end = start + max(text.count("\n"), 0)
        blocks.append(_block(kind, text, _source_ref(file_id, file_format, start, end, kind)))
    if not blocks:
        return 切正则(content, file_id, file_format, rules)
    return blocks


def 按规则切块(content: str, file_id: int, file_format: str, rules: dict) -> list[dict[str, object]]:
    mode = str(rules.get("split_mode", "regex"))
    if mode == "python_ast":
        return 切python(content, file_id, file_format, rules)
    if mode == "html":
        return 切html(content, file_id, file_format, rules)
    return 切正则(content, file_id, file_format, rules)


def parse_code_bytes(
    file_id: int,
    raw: bytes,
    ext: str,
    metadata: dict[str, object] | None = None,
    rules: dict | None = None,
) -> dict[str, object]:
    normalized = ext.lower().lstrip(".")
    if normalized not in SUPPORTED_EXTS:
        raise CodeParseError(f"Unsupported format '{normalized}'")
    rules = rules if isinstance(rules, dict) else 加载切块规则()
    content, encoding = 解码文本(raw)
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = 按规则切块(content, file_id, normalized, rules)
    result_metadata = dict(metadata or {})
    result_metadata.update({
        "encoding": encoding,
        "parser": MODULE_KEY,
        "format": normalized,
        "language": rules.get("language", normalized),
        "rules_path": str(RULES_PATH.name),
        "block_count": len(blocks),
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "content_type": "code",
        "title": f"{normalized} code",
        "source_file_id": file_id,
        "source_module": MODULE_KEY,
        "parser": MODULE_KEY,
        "source": {
            "module": MODULE_KEY,
            "file_id": file_id,
            "filename": None,
            "mime_type": None,
            "format": normalized,
        },
        "file_id": file_id,
        "format": normalized,
        "blocks": blocks,
        "resources": [],
        "metadata": result_metadata,
        "warnings": [],
    }


def parse_code_file(file_id: int, path: Path | str, ext: str) -> dict[str, object]:
    rules = 加载切块规则()
    max_bytes = int(rules.get("max_bytes", MAX_TEXT_BYTES_DEFAULT))
    full_path = Path(path)
    raw, meta = 读文件样本(full_path, max_bytes=max_bytes)
    result = parse_code_bytes(file_id, raw, ext, metadata=meta, rules=rules)
    result["title"] = full_path.name
    result["source"]["filename"] = full_path.name
    result["metadata"]["filename"] = full_path.name
    return result
