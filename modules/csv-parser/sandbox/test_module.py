"""Sandbox test for csv-parser module.

Validates CSV parsing into unified blocks/resources shape.
"""
import csv
from pathlib import Path

SDIR = Path(__file__).resolve().parent / "samples"
ALLOWED_EXTS = {"csv", "tsv"}


def _detect_delimiter(head: str) -> str:
    if "\t" in head:
        return "\t"
    if ";" in head:
        return ";"
    return ","


def parse_csv(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    blocks = []
    lines = content.strip().splitlines()
    if not lines:
        return {"file_id": 0, "format": path.suffix.lstrip(".").lower(), "blocks": [], "resources": []}

    delimiter = _detect_delimiter(lines[0])
    reader = csv.reader(lines, delimiter=delimiter)
    rows = list(reader)
    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    summary = f"表格：{len(headers)}列 x {len(data_rows)}行数据"
    if headers:
        summary += f"\n表头：{' | '.join(headers)}"
    blocks.append({"type": "段落", "text": summary, "page": None, "resource_ref": None})

    if headers:
        blocks.append({"type": "表格", "text": " | ".join(headers), "page": None, "resource_ref": None})

    for i, row in enumerate(data_rows):
        line_num = i + 2
        cols = " | ".join(row)
        blocks.append({"type": "表格", "text": f"行{line_num}：{cols}", "page": None, "resource_ref": None})

    return {"file_id": 0, "format": "csv", "blocks": blocks, "resources": []}


def validate(result: dict[str, object], label: str) -> None:
    assert all(k in result for k in ("file_id", "blocks", "resources"))
    blocks = result["blocks"]
    assert isinstance(blocks, list)
    for b in blocks:
        assert isinstance(b, dict)
        assert all(k in b for k in ("type", "text", "page", "resource_ref"))
    print(f"  [{label}] Validation PASS ({len(blocks)} blocks)")


def main() -> None:
    print("=" * 60)
    print("csv-parser sandbox test")
    print("=" * 60)
    sample = SDIR / "sample.csv"
    assert sample.exists(), f"Sample not found: {sample}"

    result = parse_csv(sample)
    for b in result["blocks"]:
        text = b["text"][:60]
        print(f"  [{b['type']}] {text}")

    validate(result, "sample.csv")
    assert len(result["blocks"]) >= 3, "Expected at least 3 blocks (summary + header + data)"
    assert result["format"] == "csv"

    print("PASS: csv-parser sandbox test")


if __name__ == "__main__":
    main()
