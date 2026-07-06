"""Tests for knowledge parser orchestration."""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-knowledge-parsing-service")

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from modules.knowledge.backend.services import parsing_service


def _parser_result(fmt: str) -> dict:
    return {
        "format": fmt,
        "blocks": [
            {
                "type": "段落",
                "text": "parser result with enough content for quality threshold",
            }
        ],
    }


@pytest.mark.asyncio
async def test_parse_document_requests_local_image_vision(monkeypatch) -> None:
    calls = []

    async def fake_call_capability(module_key, action, params, caller):
        calls.append((module_key, action, params, caller))
        return _parser_result("png")

    monkeypatch.setattr(parsing_service, "call_capability", fake_call_capability)

    doc_ir = await parsing_service.parse_document(123, "PNG", "knowledge-test")

    assert doc_ir.format == "png"
    assert calls == [
        (
            "image-vision",
            "describe",
            {"file_id": 123, "analysis_mode": "local"},
            "knowledge-test",
        )
    ]


@pytest.mark.asyncio
async def test_parse_document_keeps_non_image_parser_params_minimal(monkeypatch) -> None:
    calls = []

    async def fake_call_capability(module_key, action, params, caller):
        calls.append((module_key, action, params, caller))
        return _parser_result("txt")

    monkeypatch.setattr(parsing_service, "call_capability", fake_call_capability)

    doc_ir = await parsing_service.parse_document(456, "txt", "knowledge-test")

    assert doc_ir.format == "txt"
    assert calls == [
        (
            "text-parser",
            "parse",
            {"file_id": 456},
            "knowledge-test",
        )
    ]
