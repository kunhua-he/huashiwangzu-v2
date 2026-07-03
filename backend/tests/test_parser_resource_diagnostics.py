import pytest
from app.services.parser_resource_diagnostics import (
    build_resource_diagnostic,
    store_extracted_resources_with_diagnostics,
)


@pytest.mark.asyncio
async def test_store_extracted_resources_records_success_and_removes_private_bytes():
    async def fake_store(module: str, action: str, params: dict, caller: str) -> dict:
        assert module == "content"
        assert action == "store_resource"
        assert caller == "user:7"
        assert params["filename"] == "image.png"
        assert params["data_b64"] == "AAAA"
        return {"id": 123}

    result = {
        "file_id": 1,
        "format": "docx",
        "blocks": [{"type": "image", "text": "", "resource_ref": 1}],
        "resources": [{
            "id": 1,
            "type": "image",
            "mime_type": "image/png",
            "filename": "image.png",
            "description": "embedded",
            "_bytes_b64": "AAAA",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:7",
        parser="docx-parser",
        store_callable=fake_store,
    )

    resource = parsed["resources"][0]
    assert "_bytes_b64" not in resource
    assert resource["stored_resource_id"] == 123
    assert parsed["resource_diagnostics"] == [{
        "parser": "docx-parser",
        "stage": "store",
        "status": "stored",
        "code": "resource_stored",
        "message": "Embedded resource was stored successfully.",
        "resource_ref": 1,
        "resource_type": "image",
        "mime_type": "image/png",
        "location": {
            "resource_id": 1,
            "filename": "image.png",
            "description": "embedded",
            "stored_resource_id": 123,
        },
    }]


@pytest.mark.asyncio
async def test_store_extracted_resources_records_store_failure_without_failing_parse():
    async def broken_store(_module: str, _action: str, _params: dict, _caller: str) -> dict:
        raise RuntimeError("disk full")

    result = {
        "file_id": 2,
        "format": "pptx",
        "blocks": [{"type": "paragraph", "text": "kept"}],
        "resources": [{
            "id": 5,
            "type": "image",
            "page": 3,
            "mime_type": "image/png",
            "filename": "slide3.png",
            "_bytes_b64": "AAAA",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:8",
        parser="pptx-parser",
        store_callable=broken_store,
    )

    assert parsed["blocks"][0]["text"] == "kept"
    assert "_bytes_b64" not in parsed["resources"][0]
    assert "stored_resource_id" not in parsed["resources"][0]
    diagnostic = parsed["resource_diagnostics"][0]
    assert diagnostic["parser"] == "pptx-parser"
    assert diagnostic["stage"] == "store"
    assert diagnostic["status"] == "failed"
    assert diagnostic["code"] == "resource_store_failed"
    assert diagnostic["resource_ref"] == 5
    assert diagnostic["location"]["page"] == 3
    assert diagnostic["location"]["filename"] == "slide3.png"
    assert diagnostic["error_type"] == "RuntimeError"
    assert diagnostic["error_message"] == "disk full"


@pytest.mark.asyncio
async def test_store_extracted_resources_records_missing_bytes_as_degraded():
    calls = []

    async def fake_store(module: str, action: str, params: dict, caller: str) -> dict:
        calls.append((module, action, params, caller))
        return {"id": 1}

    result = {
        "resources": [{
            "id": 9,
            "type": "image",
            "page": 4,
            "mime_type": "image/png",
            "filename": "page4.png",
            "_bytes_b64": "",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:9",
        parser="pdf-parser",
        store_callable=fake_store,
    )

    assert calls == []
    assert "_bytes_b64" not in parsed["resources"][0]
    diagnostic = parsed["resource_diagnostics"][0]
    assert diagnostic["stage"] == "extract"
    assert diagnostic["status"] == "degraded"
    assert diagnostic["code"] == "resource_bytes_missing"
    assert diagnostic["location"]["resource_id"] == 9
    assert diagnostic["location"]["page"] == 4


@pytest.mark.asyncio
async def test_store_extracted_resources_does_not_duplicate_recorded_extract_failure():
    result = {
        "resource_diagnostics": [{
            "parser": "pdf-parser",
            "stage": "extract",
            "status": "degraded",
            "code": "resource_extract_failed",
            "message": "render failed",
            "resource_ref": 9,
        }],
        "resources": [{
            "id": 9,
            "type": "image",
            "page": 4,
            "filename": "page4.png",
            "_resource_diagnostic_recorded": True,
            "_bytes_b64": "",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:9",
        parser="pdf-parser",
        store_callable=lambda *_args: None,
    )

    assert "_resource_diagnostic_recorded" not in parsed["resources"][0]
    assert "_bytes_b64" not in parsed["resources"][0]
    assert len(parsed["resource_diagnostics"]) == 1
    assert parsed["resource_diagnostics"][0]["code"] == "resource_extract_failed"


@pytest.mark.asyncio
async def test_store_extracted_resources_records_explicit_failure_response():
    async def failed_store(_module: str, _action: str, _params: dict, _caller: str) -> dict:
        return {"success": False, "error": "quota exceeded"}

    result = {
        "resources": [{
            "id": 3,
            "type": "image",
            "filename": "image.png",
            "_bytes_b64": "AAAA",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:3",
        parser="docx-parser",
        store_callable=failed_store,
    )

    diagnostic = parsed["resource_diagnostics"][0]
    assert diagnostic["status"] == "failed"
    assert diagnostic["code"] == "resource_store_failed"
    assert diagnostic["error_message"] == "quota exceeded"
    assert "stored_resource_id" not in parsed["resources"][0]


@pytest.mark.asyncio
async def test_store_extracted_resources_requires_traceable_stored_id():
    async def no_id_store(_module: str, _action: str, _params: dict, _caller: str) -> dict:
        return {"ok": True}

    result = {
        "resources": [{
            "id": 4,
            "type": "image",
            "filename": "image.png",
            "_bytes_b64": "AAAA",
        }],
    }

    parsed = await store_extracted_resources_with_diagnostics(
        result,
        caller="user:4",
        parser="docx-parser",
        store_callable=no_id_store,
    )

    diagnostic = parsed["resource_diagnostics"][0]
    assert diagnostic["status"] == "failed"
    assert diagnostic["code"] == "resource_store_missing_id"
    assert "stored_resource_id" not in parsed["resources"][0]


def test_build_resource_diagnostic_keeps_explicit_location():
    diagnostic = build_resource_diagnostic(
        parser="pdf-parser",
        stage="extract",
        status="degraded",
        code="resource_extract_failed",
        message="render failed",
        resource={"id": 2, "type": "image", "filename": "page1.png"},
        location={"page": 1, "object": "xref:12"},
        error=ValueError("bad image"),
    )

    assert diagnostic["location"] == {
        "resource_id": 2,
        "filename": "page1.png",
        "page": 1,
        "object": "xref:12",
    }
    assert diagnostic["error_type"] == "ValueError"
    assert diagnostic["error_message"] == "bad image"
