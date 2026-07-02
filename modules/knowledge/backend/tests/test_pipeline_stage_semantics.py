import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (REPO_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_service(service_name: str):
    suffix = f".{service_name}"
    for module_name, module in sys.modules.items():
        if module_name.endswith(suffix):
            return module
    return importlib.import_module(f"modules.knowledge.backend.services.{service_name}")


pipeline_orchestrator = _load_service("pipeline_orchestrator")
fusion_service = _load_service("fusion_service")
raw_collection_service = _load_service("raw_collection_service")
StageDef = pipeline_orchestrator.StageDef
classify_fusion_status = fusion_service.classify_fusion_status
classify_raw_collection_status = raw_collection_service.classify_raw_collection_status


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDocument:
    id = 123
    raw_status = "pending"
    fusion_status = "pending"


class _FakeDb:
    def __init__(self):
        self.doc = _FakeDocument()
        self.commits = 0

    async def execute(self, _stmt):
        return _ScalarResult(self.doc)

    async def commit(self):
        self.commits += 1


def test_raw_collection_classifies_all_empty_as_degraded_or_failed():
    assert classify_raw_collection_status(
        total_rounds=3,
        valid_rounds=0,
        failed_rounds=0,
        task_count=3,
    ) == "degraded"
    assert classify_raw_collection_status(
        total_rounds=3,
        valid_rounds=0,
        failed_rounds=3,
        task_count=3,
    ) == "failed"


def test_raw_collection_classifies_partial_empty_as_degraded():
    assert classify_raw_collection_status(
        total_rounds=3,
        valid_rounds=1,
        failed_rounds=0,
        task_count=3,
    ) == "degraded"


def test_fusion_classifies_all_empty_and_index_failure():
    assert classify_fusion_status(total_pages=2, valid_pages=0) == "degraded"
    assert classify_fusion_status(total_pages=2, valid_pages=0, error_pages=2) == "failed"
    assert classify_fusion_status(total_pages=2, valid_pages=2, index_error="embed down") == "degraded"


@pytest.mark.asyncio
async def test_orchestrator_failed_stage_returns_failed(monkeypatch):
    async def fail_stage(**_kwargs):
        return {"status": "failed", "reason": "boom"}

    monkeypatch.setattr(
        pipeline_orchestrator,
        "STAGE_REGISTRY",
        [StageDef("raw", ["source_file"], False, fail_stage)],
    )
    monkeypatch.setattr(pipeline_orchestrator, "detect_stale_stages", _always_stale)
    monkeypatch.setattr(pipeline_orchestrator, "record_artifact_hash", _noop)

    result = await pipeline_orchestrator.run_pipeline(_FakeDb(), 123, 1, 456, 1)

    assert result["status"] == "failed"
    assert result["steps"]["raw"]["stage_status"] == "failed"


@pytest.mark.asyncio
async def test_orchestrator_degraded_empty_required_stage_skips_downstream(monkeypatch):
    async def empty_raw(**_kwargs):
        return {
            "status": "degraded",
            "total_rounds": 1,
            "valid_rounds": 0,
            "empty_rounds": 1,
        }

    async def fusion_stage(**_kwargs):
        return {"status": "done", "valid_pages": 1, "total_pages": 1}

    monkeypatch.setattr(
        pipeline_orchestrator,
        "STAGE_REGISTRY",
        [
            StageDef("raw", ["source_file"], False, empty_raw),
            StageDef("fusion", ["raw"], False, fusion_stage, requires=["raw"]),
        ],
    )
    monkeypatch.setattr(pipeline_orchestrator, "detect_stale_stages", _always_stale)
    monkeypatch.setattr(pipeline_orchestrator, "record_artifact_hash", _noop)

    result = await pipeline_orchestrator.run_pipeline(_FakeDb(), 123, 1, 456, 1)

    assert result["status"] == "degraded"
    assert result["steps"]["raw"]["stage_status"] == "degraded"
    assert result["steps"]["fusion"]["status"] == "skipped"
    assert result["steps"]["fusion"]["classification"] == "degraded_dependency"


@pytest.mark.asyncio
async def test_orchestrator_required_skipped_stage_degrades_pipeline(monkeypatch):
    async def skipped_raw(**_kwargs):
        return {"status": "skipped", "reason": "no usable raw"}

    async def fusion_stage(**_kwargs):
        return {"status": "done", "valid_pages": 1, "total_pages": 1}

    monkeypatch.setattr(
        pipeline_orchestrator,
        "STAGE_REGISTRY",
        [
            StageDef("raw", ["source_file"], False, skipped_raw),
            StageDef("fusion", ["raw"], False, fusion_stage, requires=["raw"]),
        ],
    )
    monkeypatch.setattr(pipeline_orchestrator, "detect_stale_stages", _always_stale)
    monkeypatch.setattr(pipeline_orchestrator, "record_artifact_hash", _noop)

    result = await pipeline_orchestrator.run_pipeline(_FakeDb(), 123, 1, 456, 1)

    assert result["status"] == "degraded"
    assert result["steps"]["raw"]["stage_status"] == "degraded"
    assert result["steps"]["fusion"]["status"] == "skipped"


async def _always_stale(*_args, **_kwargs):
    return ["raw", "fusion"]


async def _noop(*_args, **_kwargs):
    return None
