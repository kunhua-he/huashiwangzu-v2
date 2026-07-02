"""Sandbox test for email-parser module.

Validates EML parsing into header blocks, body blocks, and attachment resources.
"""
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from pathlib import Path

SDIR = Path(__file__).resolve().parent / "samples"


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _extract_body(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload:
        content_type = part.get_content_type()
        if content_type == "text/plain":
            try:
                return payload.decode("utf-8", errors="replace")
            except (UnicodeDecodeError, LookupError):
                return payload.decode("latin-1", errors="replace")
        elif content_type == "text/html":
            try:
                text = payload.decode("utf-8", errors="replace")
            except (UnicodeDecodeError, LookupError):
                text = payload.decode("latin-1", errors="replace")
            import re
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
    return ""


def parse_eml(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    msg = message_from_bytes(raw)
    blocks = []
    resources = []
    resource_counter = 0

    headers = {
        "from": _decode_header_value(msg.get("From", "")),
        "to": _decode_header_value(msg.get("To", "")),
        "subject": _decode_header_value(msg.get("Subject", "")),
        "date": msg.get("Date", ""),
    }

    blocks.append({"type": "标题", "text": f"邮件：{headers['subject'] or '(无主题)'}", "page": None, "resource_ref": None})
    header_text = f"发件人：{headers['from'] or '未知'}\n收件人：{headers['to'] or '未知'}\n日期：{headers['date'] or '未知'}"
    blocks.append({"type": "段落", "text": header_text, "page": None, "resource_ref": None})

    if msg.is_multipart():
        body_parts = []
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd.lower():
                resource_counter += 1
                filename = part.get_filename() or f"attachment_{resource_counter}"
                resources.append({
                    "id": resource_counter,
                    "type": "附件",
                    "file_storage_id": None,
                    "text_desc": _decode_header_value(filename),
                })
                continue
            body_text = _extract_body(part)
            if body_text.strip():
                body_parts.append(body_text.strip())
        if body_parts:
            blocks.append({"type": "段落", "text": "\n\n".join(body_parts), "page": None, "resource_ref": None})
    else:
        body = _extract_body(msg)
        if body.strip():
            blocks.append({"type": "段落", "text": body.strip(), "page": None, "resource_ref": None})

    return {"file_id": 0, "format": "email", "blocks": blocks, "resources": resources}


def validate(result: dict[str, object], label: str) -> None:
    assert all(k in result for k in ("file_id", "format", "blocks", "resources"))
    blocks = result["blocks"]
    resources = result["resources"]
    assert isinstance(blocks, list)
    assert isinstance(resources, list)
    for b in blocks:
        assert isinstance(b, dict)
        assert all(k in b for k in ("type", "text", "page", "resource_ref"))
    for r in resources:
        assert isinstance(r, dict)
        assert all(k in r for k in ("id", "type", "file_storage_id", "text_desc"))
    print(f"  [{label}] Validation PASS ({len(blocks)} blocks, {len(resources)} resources)")


def main() -> None:
    print("=" * 60)
    print("email-parser sandbox test")
    print("=" * 60)
    sample = SDIR / "sample.eml"
    assert sample.exists(), f"Sample not found: {sample}"

    result = parse_eml(sample)
    for b in result["blocks"]:
        text = b["text"][:60]
        print(f"  [{b['type']}] {text}")

    validate(result, "sample.eml")
    assert result["format"] == "email"
    assert "发件人" in result["blocks"][1]["text"]

    print("PASS: email-parser sandbox test")


if __name__ == "__main__":
    main()
