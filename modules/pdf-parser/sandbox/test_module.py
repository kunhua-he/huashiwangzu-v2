"""Sandbox test for pdf-parser module.
Validates that PDF parsing produces the unified content block skeleton.
Usage: python test_module.py  (from modules/pdf-parser/sandbox/)
"""
import sys
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent / "samples" / "sample.pdf"
if not SAMPLE.exists():
    print("ERROR: sample.pdf not found")
    sys.exit(1)

import pdfplumber


def parse_pdf(path: Path) -> dict:
    blocks = []
    resources = []
    resource_counter = 0
    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            pno = page_idx + 1
            text = page.extract_text() or ""
            lines = [l.rstrip() for l in text.splitlines() if l.strip()]
            if lines:
                block_text = "\n".join(lines).strip()
                if block_text:
                    block_type = "标题" if pno == 1 and len(lines) <= 5 else "段落"
                    blocks.append({"type": block_type, "text": block_text, "page": pno, "resource_ref": None})
            for table in (page.extract_tables() or []):
                if not table:
                    continue
                rows = []
                for row in table:
                    cells = [str(c).strip() if c else "" for c in row]
                    rows.append(" | ".join(cells))
                table_text = "\n".join(rows)
                if table_text.strip():
                    blocks.append({"type": "表格", "text": table_text, "page": pno, "resource_ref": None})
            for img in page.images:
                resource_counter += 1
                xref = img.get("xref") or img.get("name", "")
                blocks.append({"type": "图片", "text": "", "page": pno, "resource_ref": resource_counter})
                resources.append({"id": resource_counter, "type": "图片", "file_storage_id": None,
                                  "text_desc": f"PDF page {pno} embedded image (xref={xref})"})
    return {"file_id": 0, "format": "pdf", "blocks": blocks, "resources": resources}


def validate(result: dict):
    assert isinstance(result, dict) and all(k in result for k in ("file_id","format","blocks","resources"))
    assert result["format"] == "pdf"
    for b in result["blocks"]:
        assert all(k in b for k in ("type","text","page","resource_ref"))
        assert b["type"] in ("标题","段落","表格","图片")
    for r in result["resources"]:
        assert all(k in r for k in ("id","type","file_storage_id","text_desc"))
    print("  Validation PASS (%d blocks, %d resources)" % (len(result["blocks"]), len(result["resources"])))


def main():
    print("=" * 60)
    print("pdf-parser sandbox test")
    print("=" * 60)
    result = parse_pdf(SAMPLE)
    print("\nParsed content:")
    for b in result["blocks"]:
        print("    [%s] p=%s text=%s" % (b["type"], b["page"], b["text"][:70]))
    print("\nResources:")
    for r in result["resources"]:
        print("    [%s] %s" % (r["type"], r["text_desc"][:70]))
    validate(result)
    print("\nPASS: pdf-parser sandbox test")


if __name__ == "__main__":
    main()
