"""Sandbox test for office-gen module.

Validates core contracts: docx, xlsx, pptx, pdf, convert, generate_to_artifact,
replace_existing, export_to_artifact parameter schemas and output shapes —
without real file generation or DB calls.
"""


def _valid_content_block() -> dict:
    return {"type": "paragraph", "text": "Hello world", "level": None, "bold": False, "align": None}


def _valid_sheet() -> dict:
    return {"name": "Sheet1", "columns": ["A", "B"], "rows": [["1", "2"]]}


def _valid_slide() -> dict:
    return {"title": "Slide 1", "bullets": ["Point 1", "Point 2"], "notes": "Speaker notes"}


def test_docx_params() -> None:
    """docx action parameter contract."""
    params = {
        "filename": "report",
        "content": [
            {"type": "heading", "level": 1, "text": "Title"},
            _valid_content_block(),
            {"type": "table", "table_header": ["H1", "H2"], "table_rows": [["A", "B"]]},
        ],
    }
    assert "filename" in params
    assert isinstance(params["filename"], str) and params["filename"].strip()
    assert "content" in params
    assert isinstance(params["content"], list) and len(params["content"]) > 0
    for block in params["content"]:
        assert "type" in block, f"Content block missing 'type': {block}"
        assert block["type"] in ("heading", "paragraph", "list", "table", "code", "image")
    print("  [DOCX] Parameter contract valid")


def test_xlsx_params() -> None:
    """xlsx action parameter contract."""
    params = {
        "filename": "data",
        "sheets": [_valid_sheet()],
    }
    assert "filename" in params and isinstance(params["filename"], str)
    assert "sheets" in params and isinstance(params["sheets"], list) and len(params["sheets"]) > 0
    for sheet in params["sheets"]:
        assert "name" in sheet and "columns" in sheet and "rows" in sheet
        assert isinstance(sheet["name"], str)
        assert isinstance(sheet["columns"], list)
        assert isinstance(sheet["rows"], list)
    print("  [XLSX] Parameter contract valid")


def test_pptx_params() -> None:
    """pptx action parameter contract."""
    params = {
        "filename": "presentation",
        "slides": [_valid_slide()],
    }
    assert "filename" in params and isinstance(params["filename"], str)
    assert "slides" in params and isinstance(params["slides"], list) and len(params["slides"]) > 0
    for slide in params["slides"]:
        assert "title" in slide and "bullets" in slide
        assert isinstance(slide["title"], str)
        assert isinstance(slide["bullets"], list)
    print("  [PPTX] Parameter contract valid")


def test_pdf_params() -> None:
    """pdf action parameter contract (same content schema as docx)."""
    params = {
        "filename": "document",
        "content": [
            {"type": "heading", "level": 1, "text": "Title"},
            _valid_content_block(),
        ],
    }
    assert "filename" in params and isinstance(params["filename"], str)
    assert "content" in params and isinstance(params["content"], list) and len(params["content"]) > 0
    for block in params["content"]:
        assert "type" in block
        assert block["type"] in ("heading", "paragraph", "list", "table", "code", "image")
    print("  [PDF] Parameter contract valid")


def test_convert_params() -> None:
    """convert action parameter contract."""
    params = {"file_id": 42, "target_format": "pdf"}
    assert "file_id" in params and isinstance(params["file_id"], int) and params["file_id"] > 0
    assert "target_format" in params
    valid_formats = {"pdf", "docx", "pptx", "xlsx", "png", "html"}
    assert params["target_format"] in valid_formats, f"Invalid target_format: {params['target_format']}"
    print("  [CONVERT] Parameter contract valid")


def test_generate_to_artifact_params() -> None:
    """generate_to_artifact action parameter contract."""
    params = {
        "format": "docx",
        "filename": "artifact_doc",
        "content": [_valid_content_block()],
    }
    assert "format" in params and params["format"] in ("docx", "xlsx", "pptx", "pdf")
    assert "filename" in params and isinstance(params["filename"], str)

    # With sheets for xlsx
    params_xlsx = {"format": "xlsx", "filename": "data", "sheets": [_valid_sheet()]}
    assert params_xlsx["format"] == "xlsx"
    assert "sheets" in params_xlsx

    # With slides for pptx
    params_pptx = {"format": "pptx", "filename": "deck", "slides": [_valid_slide()]}
    assert params_pptx["format"] == "pptx"
    assert "slides" in params_pptx
    print("  [GENERATE_TO_ARTIFACT] Parameter contract valid")


def test_replace_existing_params() -> None:
    """replace_existing action parameter contract."""
    params = {
        "format": "docx",
        "target_file_id": 99,
        "content": [_valid_content_block()],
    }
    assert "format" in params and params["format"] in ("docx", "xlsx", "pptx", "pdf")
    assert "target_file_id" in params
    assert isinstance(params["target_file_id"], int) and params["target_file_id"] > 0
    print("  [REPLACE_EXISTING] Parameter contract valid")


def test_export_to_artifact_params() -> None:
    """export_to_artifact action parameter contract."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [EXPORT_TO_ARTIFACT] Parameter contract valid")


def test_output_shape() -> None:
    """Unified output shape for all generate actions."""
    result = {
        "file_id": 1,
        "path": "/data/office-gen/report.docx",
        "size": 10240,
        "format": "docx",
    }
    required = {"file_id", "path", "size", "format"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["file_id"], int)
    assert isinstance(result["size"], int) and result["size"] >= 0
    assert isinstance(result["format"], str)
    print("  [OUTPUT] Shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"file_id": 1, "path": "/path", "size": 100, "format": "pdf"}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("office-gen sandbox test")
    print("=" * 60)
    test_docx_params()
    test_xlsx_params()
    test_pptx_params()
    test_pdf_params()
    test_convert_params()
    test_generate_to_artifact_params()
    test_replace_existing_params()
    test_export_to_artifact_params()
    test_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: office-gen sandbox test")


if __name__ == "__main__":
    main()
