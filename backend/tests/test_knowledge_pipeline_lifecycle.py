import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarListResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _FakeDocument:
    id = 7
    owner_id = 4
    file_id = 99
    deleted = False
    parse_status = "parsing"
    vector_status = "indexing"
    raw_status = "collecting"
    fusion_status = "running"
    parse_error = None


class _FakeDb:
    def __init__(self, doc):
        self.doc = doc
        self.commits = 0

    async def execute(self, _stmt):
        return _ScalarResult(self.doc)

    async def commit(self):
        self.commits += 1


class _FakeSessionFactory:
    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_exc_info):
        return None


def _load_knowledge_module(module_suffix: str):
    module_names = (
        f"huashiwangzu_modules.knowledge.{module_suffix}",
        f"modules.knowledge.backend.{module_suffix}",
    )
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is not None:
            return module
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except Exception:
            continue
    raise AssertionError(f"Cannot load knowledge module {module_suffix}")


def _load_pipeline_modules():
    return (
        _load_knowledge_module("services.pipeline_service"),
        _load_knowledge_module("services.source_file_state"),
    )


@pytest.mark.asyncio
async def test_kb_pipeline_skips_when_source_file_is_deleted(monkeypatch) -> None:
    pipeline_service, source_state = _load_pipeline_modules()
    doc = _FakeDocument()
    db = _FakeDb(doc)

    async def fake_raise_if_source_unavailable(_db, _file_id):
        raise source_state.SourceFileUnavailable(99, "source_file_deleted")

    async def fake_get_source_file_availability(_db, _file_id):
        return source_state.SourceFileAvailability(False, "source_file_deleted")

    monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", _FakeSessionFactory(db))
    monkeypatch.setattr(
        pipeline_service,
        "raise_if_source_unavailable",
        fake_raise_if_source_unavailable,
    )
    monkeypatch.setattr(
        pipeline_service,
        "get_source_file_availability",
        fake_get_source_file_availability,
    )

    result = await pipeline_service._pipeline_handler({
        "document_id": doc.id,
        "user_id": doc.owner_id,
    })

    assert result["status"] == "skipped"
    assert result["reason"] == "source_file_deleted"
    assert doc.parse_error == "source_file_deleted"
    assert doc.raw_status == "pending"
    assert doc.fusion_status == "pending"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_kb_pipeline_skips_when_source_file_is_missing(monkeypatch) -> None:
    pipeline_service, source_state = _load_pipeline_modules()
    doc = _FakeDocument()
    db = _FakeDb(doc)

    async def fake_raise_if_source_unavailable(_db, _file_id):
        raise source_state.SourceFileUnavailable(99, "source_file_missing")

    async def fake_get_source_file_availability(_db, _file_id):
        return source_state.SourceFileAvailability(False, "source_file_missing")

    monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", _FakeSessionFactory(db))
    monkeypatch.setattr(
        pipeline_service,
        "raise_if_source_unavailable",
        fake_raise_if_source_unavailable,
    )
    monkeypatch.setattr(
        pipeline_service,
        "get_source_file_availability",
        fake_get_source_file_availability,
    )

    result = await pipeline_service._pipeline_handler({
        "document_id": doc.id,
        "user_id": doc.owner_id,
    })

    assert result["status"] == "skipped"
    assert result["reason"] == "source_file_missing"
    assert doc.parse_error == "source_file_missing"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_kb_pipeline_still_fails_when_active_source_content_is_broken(monkeypatch) -> None:
    pipeline_service, source_state = _load_pipeline_modules()
    doc = _FakeDocument()
    db = _FakeDb(doc)

    async def fake_raise_if_source_unavailable(_db, _file_id):
        return None

    async def fake_run_pipeline(*_args, **_kwargs):
        raise RuntimeError("File content is missing on disk")

    async def fake_get_source_file_availability(_db, _file_id):
        return source_state.SourceFileAvailability(True, "")

    monkeypatch.setattr(pipeline_service, "AsyncSessionLocal", _FakeSessionFactory(db))
    monkeypatch.setattr(
        pipeline_service,
        "raise_if_source_unavailable",
        fake_raise_if_source_unavailable,
    )
    monkeypatch.setattr(pipeline_service, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        pipeline_service,
        "get_source_file_availability",
        fake_get_source_file_availability,
    )

    result = await pipeline_service._pipeline_handler({
        "document_id": doc.id,
        "user_id": doc.owner_id,
    })

    assert result["status"] == "failed"
    assert result["error"] == "File content is missing on disk"


@pytest.mark.asyncio
async def test_enqueue_pipeline_task_dedupes_existing_inflight_task() -> None:
    document_service = _load_knowledge_module("services.document_service")
    from app.models.system import SystemTaskQueue

    existing = SystemTaskQueue(
        id=42,
        task_type="kb_pipeline",
        module="knowledge",
        parameters='{"document_id": 7, "user_id": 4}',
        status="running",
        creator_id=4,
    )

    class FakeDb:
        def __init__(self):
            self.added = []
            self.execute_calls = 0

        async def execute(self, _stmt, _params=None):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return _ScalarListResult([])
            return _ScalarListResult([existing])

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            raise AssertionError("flush should not run when a task is already in flight")

    db = FakeDb()
    result = await document_service.enqueue_pipeline_task(db, _FakeDocument(), 4)

    assert result == {
        "task_id": 42,
        "enqueued": False,
        "reason": "already_in_flight",
    }
    assert db.added == []


@pytest.mark.asyncio
async def test_pipeline_debt_dry_run_keeps_live_file_for_retry_or_parser_investigation() -> None:
    debt_service = _load_knowledge_module("services.pipeline_debt_service")
    from app.models.system import SystemTaskQueue

    task = SystemTaskQueue(
        id=100,
        task_type="kb_pipeline",
        module="knowledge",
        parameters='{"document_id": 7}',
        status="failed",
        error_message="File not found",
    )
    doc = _FakeDocument()
    file_row = type("LiveFile", (), {"id": 99, "deleted": False})()

    class FakeDb:
        async def execute(self, _stmt):
            return _ScalarListResult([task])

        async def get(self, model, item_id):
            if model.__name__ == "KbDocument" and item_id == 7:
                return doc
            if model.__name__ == "File" and item_id == 99:
                return file_row
            return None

    result = await debt_service.classify_pipeline_lifecycle_debt(FakeDb())

    assert result["summary"] == {"file_row_live": 1}
    assert result["items"][0]["category"] == "file_row_live"
    assert result["items"][0]["suggested_action"] == "retry_or_parser_investigation"
    assert result["items"][0]["would_set_parse_error"] is None
