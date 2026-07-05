"""Parser/Media Content IR real-sample matrix.

Each row exercises a production parser or media capability with a real sample
file, then runs normalize -> validate -> write through the Content IR services.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import app.main  # noqa: F401 - register framework/module capabilities
import pytest
from app.database import AsyncSessionLocal
from app.models.content import ContentPackage, ContentPackageVersion, ResourceRef
from app.services.content.ir_normalizer import normalize_ir
from app.services.content.ir_validator import validate_ir
from app.services.content.ir_writer import write_ir
from sqlalchemy import delete

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES = REPO_ROOT / "modules"
OWNER_ID = 99921


@dataclass(frozen=True)
class MatrixEntry:
    module: str
    sample: str
    capability: str
    producer: Callable[[int], Awaitable[dict[str, Any]]]
    debt: str = "none"


def _load_module(name: str, path: Path, package_dir: Path | None = None) -> types.ModuleType:
    if package_dir is not None:
        package_name = name.rsplit(".", 1)[0]
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
        sys.modules.setdefault(package_name, package)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_media_intelligence_pipeline() -> types.ModuleType:
    module_root = MODULES / "media-intelligence"
    package_name = "matrix_media_intelligence_backend"
    package = types.ModuleType(package_name)
    package.__path__ = [str(module_root / "backend")]  # type: ignore[attr-defined]
    sys.modules.setdefault(package_name, package)
    providers_name = f"{package_name}.providers"
    providers = types.ModuleType(providers_name)
    providers.__path__ = [str(module_root / "backend" / "providers")]  # type: ignore[attr-defined]
    sys.modules.setdefault(providers_name, providers)
    return _load_module(
        f"{package_name}.pipeline",
        module_root / "backend" / "pipeline.py",
    )


async def _direct(result: dict[str, Any]) -> dict[str, Any]:
    return result


async def _via_file_runner(
    router: types.ModuleType,
    sample_path: Path,
    ext: str,
    file_id: int,
    action: Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    async def fake_runner(
        params: dict[str, Any],
        caller: str,
        allowed_exts: set[str],
        handler: Callable[[int, object, Path, str], dict[str, Any]],
    ) -> dict[str, Any]:
        assert ext in allowed_exts
        file_obj = SimpleNamespace(name=sample_path.stem, extension=ext)
        return handler(params["file_id"], file_obj, sample_path, ext)

    with mock.patch.object(router, "run_uploaded_file_capability", fake_runner):
        return await action({"file_id": file_id}, f"user:{OWNER_ID}")


async def _text(file_id: int) -> dict[str, Any]:
    parser = _load_module(
        "matrix_text_parser",
        MODULES / "text-parser" / "backend" / "parser.py",
    )
    return await _direct(parser.parse_text_file(
        file_id,
        MODULES / "text-parser" / "sandbox" / "samples" / "sample.txt",
        "txt",
    ))


async def _markdown(file_id: int) -> dict[str, Any]:
    router = _load_module(
        "matrix_markdown_router",
        MODULES / "markdown-parser" / "backend" / "router.py",
    )
    sample = MODULES / "markdown-parser" / "sandbox" / "samples" / "sample.md"
    return await _direct(router.parse_markdown_content(sample.read_text(encoding="utf-8"), file_id))


async def _csv(file_id: int) -> dict[str, Any]:
    router = _load_module(
        "matrix_csv_router",
        MODULES / "csv-parser" / "backend" / "router.py",
    )
    return await _direct(router.parse_csv_path(
        file_id,
        MODULES / "csv-parser" / "sandbox" / "samples" / "sample.csv",
        "csv",
    ))


async def _xlsx(file_id: int) -> dict[str, Any]:
    core = _load_module(
        "matrix_xlsx_core",
        MODULES / "xlsx-parser" / "backend" / "parser_core.py",
    )
    return await _direct(core.parse_spreadsheet_file(
        file_id,
        MODULES / "xlsx-parser" / "sandbox" / "samples" / "sample.xlsx",
        "xlsx",
    ))


async def _docx(file_id: int) -> dict[str, Any]:
    parser = _load_module(
        "matrix_docx_parser",
        MODULES / "docx-parser" / "backend" / "parser.py",
    )
    return await _direct(parser.parse_docx_file(
        file_id,
        MODULES / "docx-parser" / "sandbox" / "samples" / "sample.docx",
    ))


async def _pdf(file_id: int) -> dict[str, Any]:
    router = _load_module(
        "matrix_pdf_router",
        MODULES / "pdf-parser" / "backend" / "router.py",
    )
    sample = MODULES / "pdf-parser" / "sandbox" / "samples" / "sample.pdf"
    return await _via_file_runner(router, sample, "pdf", file_id, router._parse)


async def _pptx(file_id: int) -> dict[str, Any]:
    router = _load_module(
        "matrix_pptx_router",
        MODULES / "pptx-parser" / "backend" / "router.py",
    )
    sample = MODULES / "pptx-parser" / "sandbox" / "samples" / "sample.pptx"
    return await _via_file_runner(router, sample, "pptx", file_id, router._parse)


async def _email(file_id: int) -> dict[str, Any]:
    parser = _load_module(
        "matrix_email_parser",
        MODULES / "email-parser" / "backend" / "parser.py",
    )
    return await _direct(parser.parse_email_file(
        file_id,
        MODULES / "email-parser" / "sandbox" / "samples" / "sample.eml",
        "eml",
    ))


async def _structured(file_id: int) -> dict[str, Any]:
    parser = _load_module(
        "matrix_structured_parser",
        MODULES / "structured-parser" / "backend" / "parser.py",
    )
    return await _direct(parser.parse_structured_file(
        file_id,
        MODULES / "structured-parser" / "sandbox" / "samples" / "sample.json",
        "json",
    ))


async def _image_vision(file_id: int) -> dict[str, Any]:
    analysis = _load_module(
        "matrix_image_vision_analysis",
        MODULES / "image-vision" / "backend" / "image_analysis.py",
    )
    sample = MODULES / "image-vision" / "sandbox" / "samples" / "sample.png"
    raw = sample.read_bytes()
    local = analysis.analyze_image_bytes(raw, "sample.png", "png")
    summary = analysis.build_local_summary(local)
    return await _direct(analysis.build_content_ir_output(
        file_id=file_id,
        filename="sample.png",
        extension="png",
        description=summary,
        local_summary=summary,
        local_analysis=local,
        resource_id=1,
        analysis_strategy={"mode": "local"},
        model_fallback={"fallback_used": False, "final_success": True},
        warnings=[],
    ))


async def _media_intelligence(file_id: int) -> dict[str, Any]:
    pipeline = _load_media_intelligence_pipeline()
    with tempfile.TemporaryDirectory(prefix="media-intelligence-matrix-") as tmp_dir:
        sample = Path(tmp_dir) / "clip.mp4"
        sample.write_bytes(b"not-a-real-video-but-a-real-file" * 128)
        return await pipeline.extract_keyframes_path(
            file_id,
            "clip.mp4",
            sample,
            "mp4",
            {"max_keyframes": 2, "refine": False},
        )


async def _media_asr(file_id: int) -> dict[str, Any]:
    router = _load_module(
        "matrix_media_asr.router",
        MODULES / "media-asr" / "backend" / "router.py",
        MODULES / "media-asr" / "backend",
    )

    async def fake_transcribe(_path: Path, _model: str, _language: str | None) -> dict[str, Any]:
        return {
            "text": "hello matrix",
            "segments": [{"start": 0.0, "end": 1.2, "text": "hello matrix"}],
            "duration_seconds": 1.2,
        }

    async def fake_runner(
        params: dict[str, Any],
        _caller: str,
        allowed_exts: set[str],
        handler: Callable[[int, object, Path, str], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        assert "wav" in allowed_exts
        file_obj = SimpleNamespace(name="sample.wav", extension="wav")
        return await handler(params["file_id"], file_obj, Path("/tmp/sample.wav"), "wav")

    with (
        mock.patch.object(router, "transcribe_audio_file", fake_transcribe),
        mock.patch.object(router, "run_uploaded_file_capability", fake_runner),
    ):
        return await router._transcribe_audio(
            {"file_id": file_id, "model": "tiny", "save_text": False},
            f"user:{OWNER_ID}",
        )


MATRIX_ENTRIES = [
    MatrixEntry("text-parser", "sandbox/samples/sample.txt", "parse", _text),
    MatrixEntry("markdown-parser", "sandbox/samples/sample.md", "parse", _markdown),
    MatrixEntry("csv-parser", "sandbox/samples/sample.csv", "parse", _csv),
    MatrixEntry("xlsx-parser", "sandbox/samples/sample.xlsx", "parse", _xlsx),
    MatrixEntry("docx-parser", "sandbox/samples/sample.docx", "parse", _docx),
    MatrixEntry("pdf-parser", "sandbox/samples/sample.pdf", "parse", _pdf),
    MatrixEntry("pptx-parser", "sandbox/samples/sample.pptx", "parse", _pptx),
    MatrixEntry("email-parser", "sandbox/samples/sample.eml", "parse", _email),
    MatrixEntry("structured-parser", "sandbox/samples/sample.json", "parse", _structured),
    MatrixEntry("image-vision", "sandbox/samples/sample.png", "describe", _image_vision),
    MatrixEntry(
        "media-intelligence",
        "generated-invalid-video.mp4",
        "extract_keyframes",
        _media_intelligence,
        "semantic adapters intentionally degraded when OCR/object/VLM are not configured",
    ),
    MatrixEntry(
        "media-asr",
        "stubbed-sample.wav",
        "transcribe_audio",
        _media_asr,
        "ASR model boundary stubbed; router/capability contract and timestamp IR are real",
    ),
]


async def _delete_packages(package_ids: list[int]) -> None:
    if not package_ids:
        return
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ResourceRef).where(ResourceRef.package_id.in_(package_ids)))
        await db.execute(delete(ContentPackageVersion).where(ContentPackageVersion.package_id.in_(package_ids)))
        await db.execute(delete(ContentPackage).where(ContentPackage.id.in_(package_ids)))
        await db.commit()


async def _write_matrix_ir(ir: dict[str, Any]) -> dict[str, Any]:
    ir = dict(ir)
    ir["source_file_id"] = None
    source = dict(ir.get("source") or {})
    source["file_id"] = None
    ir["source"] = source

    async with AsyncSessionLocal() as db:
        return await write_ir(db, ir, owner_id=OWNER_ID, caller=f"user:{OWNER_ID}")


def _fake_content_call(module: str, action: str, params: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
    if module == "excel-engine" and action == "create_workbook":
        return {"state_key": "matrix-workbook"}
    if module == "excel-engine" and action == "update_range":
        assert params.get("rows")
        return {"updated": True}
    if module == "content" and action == "store_resource":
        return {"data": {"id": 88001}}
    if module == "memory" and action == "save":
        return {"id": 99001}
    return {}


@pytest.mark.asyncio
async def test_parser_media_real_sample_content_ir_matrix() -> None:
    matrix: list[dict[str, Any]] = []
    package_ids: list[int] = []

    try:
        with mock.patch("app.services.content.ir_writer.call_capability", side_effect=_fake_content_call):
            for index, entry in enumerate(MATRIX_ENTRIES, start=1):
                raw = await entry.producer(index)
                normalized = await normalize_ir(raw)
                validation = await validate_ir(normalized)
                assert validation.valid, {
                    "module": entry.module,
                    "errors": [error.model_dump() for error in validation.errors],
                }
                write_result = await _write_matrix_ir(normalized)
                if write_result.get("canonical_source") == "content_package":
                    package_ids.append(int(write_result["package_id"]))

                matrix.append({
                    "module": entry.module,
                    "sample": entry.sample,
                    "capability": entry.capability,
                    "raw output": raw.get("content_type"),
                    "normalized IR": {
                        "schema_version": normalized.get("schema_version"),
                        "content_type": normalized.get("content_type"),
                        "top_blocks": [block.get("type") for block in normalized.get("blocks", [])],
                    },
                    "validate": "pass",
                    "write": write_result.get("canonical_source"),
                    "debt": entry.debt,
                })
    finally:
        await _delete_packages(package_ids)

    assert len(matrix) == 12
    assert {row["module"] for row in matrix} == {entry.module for entry in MATRIX_ENTRIES}
    assert all(row["normalized IR"]["schema_version"] == "content-ir/v1" for row in matrix)
    assert next(row for row in matrix if row["module"] == "csv-parser")["normalized IR"]["top_blocks"] == ["sheet"]
    assert next(row for row in matrix if row["module"] == "xlsx-parser")["normalized IR"]["top_blocks"] == ["sheet", "sheet"]
    asr_row = next(row for row in matrix if row["module"] == "media-asr")
    assert asr_row["write"] == "content_package"
