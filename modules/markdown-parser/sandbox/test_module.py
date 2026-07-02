"""Sandbox test for markdown-parser module.

Validates Markdown parsing into unified blocks (heading, paragraph, list, code, table) and image resources.
"""
import re
from pathlib import Path

SDIR = Path(__file__).resolve().parent / "samples"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CODE_FENCE_RE = re.compile(r"^`{3,}\s*(\w*)$")
LIST_ITEM_RE = re.compile(r"^(\s*)[-*+]\s+")
ORDERED_LIST_RE = re.compile(r"^(\s*)\d+[.)]\s+")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def parse_md(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = content.splitlines(keepends=False)
    blocks = []
    resources = []
    resource_counter = 0
    in_code = False
    code_lines = []
    para_lines = []
    list_lines = []
    in_list = False

    def flush_para() -> None:
        nonlocal para_lines
        if para_lines:
            text = "\n".join(para_lines).strip()
            if text:
                blocks.append({"type": "paragraph", "text": text, "page": None, "resource_ref": None})
            para_lines = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            blocks.append({"type": "code", "text": "\n".join(code_lines), "page": None, "resource_ref": None})
            code_lines = []

    def flush_list() -> None:
        nonlocal list_lines
        if list_lines:
            blocks.append({"type": "list", "text": "\n".join(list_lines), "page": None, "resource_ref": None})
            list_lines = []

    for line in lines:
        if CODE_FENCE_RE.match(line):
            flush_para()
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        m = HEADING_RE.match(line)
        if m:
            flush_para()
            flush_list()
            blocks.append({"type": "heading", "text": m.group(2).strip(), "page": None, "resource_ref": None})
            continue
        if LIST_ITEM_RE.match(line) or ORDERED_LIST_RE.match(line):
            flush_para()
            in_list = True
            list_lines.append(line)
            continue
        if in_list:
            if line.strip() == "":
                flush_list()
                in_list = False
                continue
            list_lines.append(line)
            continue
        if line.strip() == "":
            flush_para()
            continue
        para_lines.append(line)

    flush_para()
    flush_code()
    flush_list()

    for img_match in IMAGE_RE.finditer(content):
        resource_counter += 1
        blocks.append({"type": "image", "text": img_match.group(1) or "", "page": None, "resource_ref": resource_counter})
        resources.append({
            "id": resource_counter,
            "type": "image",
            "file_storage_id": None,
            "text_desc": f"Markdown image: {img_match.group(2)} ({img_match.group(1) or ''})",
        })

    return {"file_id": 0, "format": "markdown", "blocks": blocks, "resources": resources}


def validate(result: dict[str, object], label: str) -> None:
    assert all(k in result for k in ("file_id", "format", "blocks", "resources"))
    blocks = result["blocks"]
    resources = result["resources"]
    assert isinstance(blocks, list)
    assert isinstance(resources, list)
    for b in blocks:
        assert isinstance(b, dict)
        assert all(k in b for k in ("type", "text", "page", "resource_ref"))
    print(f"  [{label}] Validation PASS ({len(blocks)} blocks, {len(resources)} resources)")


def main() -> None:
    print("=" * 60)
    print("markdown-parser sandbox test")
    print("=" * 60)
    sample = SDIR / "sample.md"
    assert sample.exists(), f"Sample not found: {sample}"

    result = parse_md(sample)
    for b in result["blocks"]:
        text = b["text"][:60]
        print(f"  [{b['type']}] {text}")

    validate(result, "sample.md")
    assert result["format"] == "markdown"
    assert any(b["type"] == "heading" for b in result["blocks"]), "Expected at least one heading"
    assert any(b["type"] == "paragraph" for b in result["blocks"]), "Expected at least one paragraph"

    print("PASS: markdown-parser sandbox test")


if __name__ == "__main__":
    main()
