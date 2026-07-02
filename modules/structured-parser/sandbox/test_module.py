"""Sandbox test for structured-parser module.

Validates JSON/YAML parsing into flattened key-path blocks.
"""
import json
from pathlib import Path

SDIR = Path(__file__).resolve().parent / "samples"


def _flatten_json(obj: object, prefix: str = "", depth: int = 0, max_depth: int = 10) -> list[str]:
    if depth > max_depth:
        return [f"{prefix}: (max depth reached)"]
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                lines.extend(_flatten_json(v, path, depth + 1, max_depth))
            else:
                lines.append(f"{path}: {v}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                lines.extend(_flatten_json(item, path, depth + 1, max_depth))
            else:
                lines.append(f"{path}: {item}")
    else:
        lines.append(f"{prefix}: {obj}")
    return lines


def parse_structured(path: Path) -> dict[str, object]:
    content = path.read_text(encoding="utf-8").strip()
    blocks = []
    data = json.loads(content)

    lines = _flatten_json(data)
    if lines:
        summary = f"结构化数据：{len(lines)} 个字段"
        blocks.append({"type": "段落", "text": summary, "page": None, "resource_ref": None})
        batch_size = 30
        for start in range(0, len(lines), batch_size):
            batch = lines[start:start + batch_size]
            blocks.append({"type": "段落", "text": "\n".join(batch), "page": None, "resource_ref": None})

    return {"file_id": 0, "format": "json", "blocks": blocks, "resources": []}


def validate(result: dict[str, object], label: str) -> None:
    assert all(k in result for k in ("file_id", "format", "blocks", "resources"))
    blocks = result["blocks"]
    assert isinstance(blocks, list)
    for b in blocks:
        assert isinstance(b, dict)
        assert all(k in b for k in ("type", "text", "page", "resource_ref"))
    print(f"  [{label}] Validation PASS ({len(blocks)} blocks)")


def main() -> None:
    print("=" * 60)
    print("structured-parser sandbox test")
    print("=" * 60)
    sample = SDIR / "sample.json"
    assert sample.exists(), f"Sample not found: {sample}"

    result = parse_structured(sample)
    for b in result["blocks"]:
        text = b["text"][:80]
        print(f"  [{b['type']}] {text}")

    validate(result, "sample.json")
    assert result["format"] == "json"
    assert len(result["blocks"]) >= 1
    assert "name" in result["blocks"][-1]["text"] if len(result["blocks"]) > 1 else True

    print("PASS: structured-parser sandbox test")


if __name__ == "__main__":
    main()
