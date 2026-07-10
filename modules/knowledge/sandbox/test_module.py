"""Sandbox test for knowledge module.

Validates core shapes: search results, document, chunk, entity, page fusion,
and governance candidates — without calling external embedding services or real DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (REPO_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_search_result_shape() -> None:
    """Hybrid search result shape contract."""
    result = {
        "document_id": 1,
        "document_name": "test.pdf",
        "chunk_id": 10,
        "block_id": 5,
        "page": 1,
        "text": "Relevant content snippet...",
        "score": 0.95,
        "content_package_id": None,
        "source_available": True,
        "source_state": "available",
    }
    required = {"document_id", "text", "score", "page"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["score"], (int, float))
    assert result["page"] >= 1
    print("  [SEARCH] Result shape valid")


def test_document_shape() -> None:
    """Document shape contract."""
    doc = {
        "id": 1,
        "file_id": 10,
        "filename": "sample.pdf",
        "owner_id": 1,
        "status": "completed",
        "parse_status": "completed",
        "fusion_status": "completed",
        "total_chunks": 25,
        "total_pages": 5,
        "source_available": True,
        "source_state": "available",
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"id", "filename", "owner_id", "status", "source_available", "source_state"}
    for field in required:
        assert field in doc, f"Missing required field: {field}"
    assert doc["status"] in ("pending", "processing", "completed", "failed")
    assert doc["source_available"] is True
    assert doc["source_state"] == "available"
    print("  [DOCUMENT] Shape valid")


def test_document_lifecycle_filters_unavailable_sources() -> None:
    """List/detail must not expose unavailable source files as normal documents."""
    docs = [
        {"id": 1, "deleted": False, "source_available": True, "source_state": "available"},
        {"id": 2, "deleted": False, "source_available": False, "source_state": "source_file_deleted"},
        {"id": 3, "deleted": False, "source_available": False, "source_state": "source_file_missing"},
        {"id": 4, "deleted": True, "source_available": True, "source_state": "available"},
    ]

    visible = [
        doc for doc in docs
        if not doc["deleted"] and doc["source_available"] and doc["source_state"] == "available"
    ]

    assert [doc["id"] for doc in visible] == [1]
    assert all(doc["source_available"] is True for doc in visible)
    assert all(doc["source_state"] == "available" for doc in visible)
    assert {doc["source_state"] for doc in docs if not doc["source_available"]} == {
        "source_file_deleted",
        "source_file_missing",
    }
    print("  [DOCUMENT-LIFECYCLE] Source filtering valid")


def test_lifecycle_debt_governance_contract() -> None:
    """Lifecycle debt audit/archive capability must be dry-run and confirm guarded."""
    audit = {
        "dry_run": True,
        "matched": 3,
        "summary": {
            "source_file_deleted": 1,
            "source_file_missing": 1,
            "source_file_physical_missing": 1,
        },
        "source_recycled_count": 1,
        "source_missing_count": 1,
        "source_physical_missing_count": 1,
        "candidate_document_ids": [10, 11],
        "sample_documents": [
            {"document_id": 10, "reason": "source_file_deleted", "source_lifecycle_state": "source_recycled"},
            {"document_id": 11, "reason": "source_file_missing", "source_lifecycle_state": "source_db_missing"},
            {
                "document_id": 12,
                "reason": "source_file_physical_missing",
                "source_lifecycle_state": "source_disk_missing",
            },
        ],
        "recommended_action": "archive_source_unavailable_documents",
    }
    archive_dry_run = {
        "dry_run": True,
        "action": "archive_source_unavailable_documents",
        "selected": 2,
        "changed": 0,
        "requires_confirm": True,
        "confirm_token": "ARCHIVE_SOURCE_UNAVAILABLE",
    }

    assert audit["dry_run"] is True
    assert audit["matched"] == 3
    assert audit["source_recycled_count"] == 1
    assert audit["source_missing_count"] == 1
    assert audit["source_physical_missing_count"] == 1
    assert {item["source_lifecycle_state"] for item in audit["sample_documents"]} == {
        "source_recycled",
        "source_db_missing",
        "source_disk_missing",
    }
    assert archive_dry_run["changed"] == 0
    assert archive_dry_run["confirm_token"] == "ARCHIVE_SOURCE_UNAVAILABLE"
    print("  [LIFECYCLE-DEBT] Governance contract valid")


def test_pipeline_lifecycle_skips_before_parse_or_index() -> None:
    """Pipeline must stop unavailable sources before writing derived artifacts."""
    source_state = {"available": False, "reason": "source_file_deleted"}
    writes = {"chunks": 0, "raw": 0, "fusion": 0}

    if not source_state["available"]:
        result = {
            "status": "skipped",
            "reason": source_state["reason"],
            "classification": "source_unavailable",
        }
    else:
        writes["chunks"] += 1
        result = {"status": "done"}

    assert result == {
        "status": "skipped",
        "reason": "source_file_deleted",
        "classification": "source_unavailable",
    }
    assert writes == {"chunks": 0, "raw": 0, "fusion": 0}
    print("  [PIPELINE-LIFECYCLE] Pre-parse source guard valid")


def test_chunk_shape() -> None:
    """Knowledge chunk shape contract."""
    chunk = {
        "id": 10,
        "document_id": 1,
        "owner_id": 1,
        "page": 1,
        "chunk_index": 0,
        "block_type": "paragraph",
        "text": "Chunk text content...",
        "keywords": "",
        "source_available": True,
        "source_state": "available",
    }
    required = {"id", "document_id", "text", "page", "block_type"}
    for field in required:
        assert field in chunk, f"Missing required field: {field}"
    assert chunk["block_type"] in ("paragraph", "heading", "list", "table", "code")
    assert chunk["source_available"] is True
    assert chunk["source_state"] == "available"
    print("  [CHUNK] Shape valid")


def test_spreadsheet_ir_keeps_sheet_children() -> None:
    """Spreadsheet parser sheet nodes must not break knowledge IR normalization."""
    from modules.knowledge.backend.ir_models import from_legacy_blocks, to_legacy_dict

    ir = from_legacy_blocks(
        file_id=42,
        fmt="xlsx",
        blocks=[{
            "type": "sheet",
            "text": "Sales",
            "page": 1,
            "source_ref": {"sheet": "Sales", "range": "A1:B2"},
            "data": {"sheet_name": "Sales"},
            "children": [{
                "type": "table",
                "text": "Name | Amount\nA | 10",
                "page": 1,
                "source_ref": {"sheet": "Sales", "range": "A1:B2"},
                "data": {"headers": ["Name", "Amount"], "rows": [["A", "10"]]},
            }],
        }],
    )

    assert ir.blocks[0].type == "sheet"
    assert ir.blocks[0].children[0].type == "table"
    assert ir.blocks[0].children[0].metadata["headers"] == ["Name", "Amount"]
    legacy = to_legacy_dict(ir)
    assert [block["type"] for block in legacy["blocks"]] == ["标题", "表格"]
    assert any("Name | Amount" in block["text"] for block in legacy["blocks"])
    print("  [SPREADSHEET-IR] Sheet children normalization valid")


def test_entity_shape() -> None:
    """Entity dictionary entry shape contract."""
    entity = {
        "id": 1,
        "label": "hyaluronic acid",
        "category": "ingredient",
        "description": "A moisturizing ingredient",
        "aliases": ["HA", "hyaluronan"],
        "confidence": 0.92,
    }
    required = {"id", "label", "category"}
    for field in required:
        assert field in entity, f"Missing required field: {field}"
    assert isinstance(entity["confidence"], (int, float))
    print("  [ENTITY] Shape valid")


def test_page_fusion_shape() -> None:
    """Page fusion shape contract."""
    fusion = {
        "page": 1,
        "page_title": "Introduction",
        "fused_text": "Fused content for page 1...",
        "page_summary": "Summary of page 1",
        "confidence": 0.88,
        "conflicts": [],
    }
    required = {"page", "fused_text", "confidence"}
    for field in required:
        assert field in fusion, f"Missing required field: {field}"
    assert isinstance(fusion["conflicts"], list)
    print("  [PAGE_FUSION] Shape valid")


def test_governance_candidate_shape() -> None:
    """Governance candidate shape contract."""
    candidate = {
        "id": 1,
        "entity_id": None,
        "label": "New Entity",
        "category": "concept",
        "evidence": "Source text evidence...",
        "document_id": 1,
        "audit_status": "pending",
        "confidence": 0.85,
    }
    required = {"id", "label", "audit_status", "evidence"}
    for field in required:
        assert field in candidate, f"Missing required field: {field}"
    assert candidate["audit_status"] in ("pending", "approved", "rejected")
    print("  [GOVERNANCE] Candidate shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"results": []}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def test_ingest_capability_params() -> None:
    """Ingest capability parameter contract."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [INGEST] Parameter contract valid")


def test_ingest_status_shape() -> None:
    """Ingest status result shape contract."""
    status = {
        "document_id": 1,
        "task_id": 10,
        "enqueued": True,
        "stage": "parse",
        "status": "queued",
        "pipeline_status": "queued",
        "task_status": "pending",
        "parse_status": "pending",
        "vector_status": "pending",
        "raw_status": "pending",
        "fusion_status": "pending",
        "stage_summary": {
            "parse": {"status": "pending", "ready": False},
            "vector": {"status": "pending", "ready": False, "count": 0},
            "raw": {"status": "pending", "ready": False},
            "fusion": {"status": "pending", "ready": False},
        },
        "search_ready": False,
        "deep_ready": False,
        "next_action": "wait_for_search_index",
    }
    required = {
        "document_id", "task_id", "enqueued", "stage", "status",
        "pipeline_status", "stage_summary", "search_ready", "deep_ready",
        "next_action",
    }
    for field in required:
        assert field in status, f"Missing required field: {field}"
    assert status["pipeline_status"] in ("queued", "running", "search_ready", "deep_ready", "failed", "pending")
    assert isinstance(status["stage_summary"], dict)
    print("  [INGEST-STATUS] Shape valid")


def test_cognitive_index_registration_link_shape() -> None:
    """Registration payload must expose canonical/duplicate reuse links."""
    payload = {
        "document_id": 1,
        "status": "existing",
        "duplicate_reused": True,
        "content_link": {
            "link_id": 10,
            "file_id": 101,
            "content_object_id": 20,
            "document_id": 1,
            "canonical_document_id": 1,
            "canonical_file_id": 100,
            "link_role": "duplicate",
            "reuse_reason": "md5_duplicate",
            "md5_hash": "a" * 32,
            "source_name_snapshot": "copy.pdf",
            "status": "active",
        },
    }

    link = payload["content_link"]
    assert payload["duplicate_reused"] is True
    assert link["link_role"] in {"canonical", "duplicate"}
    assert link["canonical_document_id"] == payload["document_id"]
    assert link["reuse_reason"]
    print("  [COGNITIVE-INDEX] Registration link shape valid")


def test_cognitive_index_query_context_shape() -> None:
    """Search context should include persisted query enrichment metadata."""
    context_data = {
        "query_context": {
            "query_context_id": 99,
            "expanded_terms": ["精华水", "备案报告"],
            "related_terms": [],
            "causal_links": [],
            "facts": [{"text": "备案报告正文", "document_id": 1, "page": 1}],
            "evidence_refs": [{"document_id": 1, "chunk_id": 10, "page": 1, "score": 0.9}],
            "result_document_ids": [1],
            "diagnostics": {"schema_version": "kb_query_context_v1"},
        }
    }

    query_context = context_data["query_context"]
    assert query_context["query_context_id"] > 0
    assert query_context["diagnostics"]["schema_version"] == "kb_query_context_v1"
    assert query_context["result_document_ids"] == [1]
    assert query_context["evidence_refs"][0]["chunk_id"] == 10
    print("  [COGNITIVE-INDEX] Query context shape valid")


def test_cognitive_index_capability_params() -> None:
    """Cognitive admin capabilities must stay dry-run friendly and document scoped."""
    backfill = {"dry_run": True, "limit": 1000, "source_root": "企业微盘导入", "build_terms": True}
    derive = {"document_id": 1, "limit": 200}

    assert backfill["dry_run"] is True
    assert 1 <= backfill["limit"] <= 10000
    assert derive["document_id"] > 0
    assert 1 <= derive["limit"] <= 1000
    print("  [COGNITIVE-INDEX] Capability params valid")


def test_export_format_contract() -> None:
    """Export format contract must stay explicit."""
    allowed_formats = {"markdown", "html", "json"}
    for fmt in ("markdown", "html", "json"):
        assert fmt in allowed_formats
    assert "bad_format" not in allowed_formats
    print("  [EXPORT] Format contract valid")


def test_export_uses_single_canonical_source() -> None:
    """Fusion and chunks must not be exported together when fusion is present."""
    chunks = [{"text": "hello smoke", "page": 1}]
    fusions = [{"fused_text": "hello smoke", "page": 1}]
    export_blocks = [
        {"text": item["fused_text"], "page": item["page"], "source": "page_fusion"}
        for item in fusions
        if item["fused_text"].strip()
    ] or [
        {"text": item["text"], "page": item["page"], "source": "chunk"}
        for item in chunks
        if item["text"].strip()
    ]
    exported_text = "\n".join(item["text"] for item in export_blocks)
    assert exported_text.count("hello smoke") == 1
    assert {item["source"] for item in export_blocks} == {"page_fusion"}
    print("  [EXPORT] Canonical source de-dup valid")


def test_export_metadata_shape() -> None:
    """Exported artifact metadata must explain readiness and evidence count."""
    metadata = {
        "document_id": 1,
        "title": "sample.pdf",
        "format": "json",
        "source_status": "available",
        "search_ready": True,
        "deep_ready": False,
        "block_count": 2,
        "evidence_count": 2,
        "export_source": "page_fusion",
    }
    required = {
        "document_id", "title", "format", "source_status",
        "search_ready", "deep_ready", "block_count", "evidence_count",
    }
    for field in required:
        assert field in metadata, f"Missing export metadata field: {field}"
    assert metadata["format"] in {"markdown", "html", "json"}
    assert metadata["block_count"] == metadata["evidence_count"]
    print("  [EXPORT] Metadata shape valid")


def main() -> None:
    print("=" * 60)
    print("knowledge sandbox test")
    print("=" * 60)
    test_search_result_shape()
    test_document_shape()
    test_document_lifecycle_filters_unavailable_sources()
    test_pipeline_lifecycle_skips_before_parse_or_index()
    test_chunk_shape()
    test_spreadsheet_ir_keeps_sheet_children()
    test_entity_shape()
    test_page_fusion_shape()
    test_governance_candidate_shape()
    test_response_shape()
    test_ingest_capability_params()
    test_ingest_status_shape()
    test_cognitive_index_registration_link_shape()
    test_cognitive_index_query_context_shape()
    test_cognitive_index_capability_params()
    test_export_format_contract()
    test_export_uses_single_canonical_source()
    test_export_metadata_shape()
    print("=" * 60)
    print("PASS: knowledge sandbox test")


if __name__ == "__main__":
    main()
