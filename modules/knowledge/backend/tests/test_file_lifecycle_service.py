import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
for path in (REPO_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


file_lifecycle_service = importlib.import_module(
    "modules.knowledge.backend.services.file_lifecycle_service"
)


class _Doc:
    def __init__(self, doc_id: int):
        self.id = doc_id
        self.file_id = 10
        self.deleted = False
        self.parse_status = "parsing"
        self.vector_status = "indexing"
        self.raw_status = "collecting"
        self.fusion_status = "fusing"
        self.parse_error = None


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _ScalarResult(self._rows)


class _FakeSession:
    def __init__(self, docs):
        self.docs = docs
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def execute(self, _stmt):
        return _ExecuteResult(self.docs)

    async def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
async def test_file_deleted_archives_pending_pipeline_tasks(monkeypatch):
    docs = [_Doc(101), _Doc(102)]
    session = _FakeSession(docs)
    archived_calls = []

    async def fake_archive(db, document_ids):
        archived_calls.append((db, list(document_ids)))
        return {"changed": 2}

    monkeypatch.setattr(file_lifecycle_service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(
        file_lifecycle_service,
        "archive_pending_pipeline_tasks_for_documents",
        fake_archive,
    )

    result = await file_lifecycle_service._on_file_deleted(
        {"file_id": 10},
        caller="user:1",
        caller_role="admin",
    )

    assert result["documents_paused"] == 2
    assert result["pending_pipeline_tasks_archived"] == 2
    assert archived_calls == [(session, [101, 102])]
    assert session.commit_count == 1
    assert {doc.parse_error for doc in docs} == {"source_file_deleted"}
    assert all(doc.parse_status == "pending" for doc in docs)
