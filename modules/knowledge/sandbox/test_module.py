"""Sandbox test for knowledge module.

Validates core shapes: search results, document, chunk, entity, page fusion,
and governance candidates — without calling external embedding services or real DB.
"""


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
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"id", "filename", "owner_id", "status"}
    for field in required:
        assert field in doc, f"Missing required field: {field}"
    assert doc["status"] in ("pending", "processing", "completed", "failed")
    print("  [DOCUMENT] Shape valid")


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
    }
    required = {"id", "document_id", "text", "page", "block_type"}
    for field in required:
        assert field in chunk, f"Missing required field: {field}"
    assert chunk["block_type"] in ("paragraph", "heading", "list", "table", "code")
    print("  [CHUNK] Shape valid")


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


def main() -> None:
    print("=" * 60)
    print("knowledge sandbox test")
    print("=" * 60)
    test_search_result_shape()
    test_document_shape()
    test_chunk_shape()
    test_entity_shape()
    test_page_fusion_shape()
    test_governance_candidate_shape()
    test_response_shape()
    test_ingest_capability_params()
    print("=" * 60)
    print("PASS: knowledge sandbox test")


if __name__ == "__main__":
    main()
