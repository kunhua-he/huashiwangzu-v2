from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from scripts.maintenance import reset_runtime_data as reset_script


class FakeConnection:
    def __init__(self, tables: list[str]) -> None:
        self.tables = tables
        self.executed: list[str] = []
        self.closed = False

    async def fetch(self, _query: str) -> list[dict[str, str]]:
        return [{"table_name": table} for table in self.tables]

    async def execute(self, query: str) -> None:
        self.executed.append(query)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeConnection:
    conn = FakeConnection(
        [
            "framework_system_tasks",
            "framework_system_settings",
            "kb_documents",
            "agent_conversations",
            "framework_file_items",
            "unrelated_table",
        ]
    )

    async def fake_connect(**_kwargs: object) -> FakeConnection:
        return conn

    monkeypatch.setattr(reset_script.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(
        reset_script,
        "_db_config",
        lambda: reset_script.DbConfig(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="",
            name="huashiwangzu_v2",
        ),
    )
    return conn


def make_db_backup(tmp_path: Path) -> Path:
    backup = tmp_path / "db-backup"
    backup.mkdir()
    (backup / "database.sql").write_text("-- backup", encoding="utf-8")
    (backup / "manifest.json").write_text("{}", encoding="utf-8")
    return backup


def run_reset(**kwargs: object) -> dict[str, object]:
    return asyncio.run(reset_script.reset_runtime_data(**kwargs))


def test_confirm_missing_or_wrong_rejects(fake_db: FakeConnection, tmp_path: Path) -> None:
    backup = make_db_backup(tmp_path)
    with pytest.raises(SystemExit, match="Apply requires"):
        run_reset(
            apply=True,
            scope="tasks",
            clean_files=False,
            backup_dir=None,
            db_backup=backup,
            confirm="",
        )
    with pytest.raises(SystemExit, match="Apply requires"):
        run_reset(
            apply=True,
            scope="tasks",
            clean_files=False,
            backup_dir=None,
            db_backup=backup,
            confirm="RESET wrong_db",
        )
    assert fake_db.executed == []


def test_production_database_name_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        reset_script,
        "_db_config",
        lambda: reset_script.DbConfig("127.0.0.1", 5432, "postgres", "", "customer_prod"),
    )
    with pytest.raises(SystemExit, match="production-like"):
        run_reset(
            apply=False,
            scope="tasks",
            clean_files=False,
            backup_dir=None,
            db_backup=make_db_backup(tmp_path),
        )


def test_non_local_host_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        reset_script,
        "_db_config",
        lambda: reset_script.DbConfig("10.0.0.8", 5432, "postgres", "", "huashiwangzu_v2"),
    )
    with pytest.raises(SystemExit, match="non-local"):
        run_reset(
            apply=False,
            scope="tasks",
            clean_files=False,
            backup_dir=None,
            db_backup=make_db_backup(tmp_path),
        )


def test_scope_uses_explicit_allowlist(fake_db: FakeConnection, tmp_path: Path) -> None:
    result = run_reset(
        apply=True,
        scope="knowledge",
        clean_files=False,
        backup_dir=None,
        db_backup=make_db_backup(tmp_path),
        confirm="RESET huashiwangzu_v2",
    )

    assert result["truncate_tables"] == ["kb_documents"]
    assert "framework_system_settings" in result["available_tables"]
    assert "kb_chunks" in result["skipped_tables"]
    assert "unrelated_table" not in result["truncate_tables"]
    assert fake_db.executed == ['TRUNCATE TABLE "kb_documents" RESTART IDENTITY CASCADE']


def test_dry_run_does_not_truncate_or_clear_files(
    fake_db: FakeConnection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "backend" / "data" / "uploads"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "file.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(reset_script, "BACKEND_DATA_DIR", tmp_path / "backend" / "data")
    monkeypatch.setattr(reset_script, "RUNTIME_DIRS", [runtime_dir])

    result = run_reset(
        apply=False,
        scope="files",
        clean_files=True,
        backup_dir=None,
        db_backup=None,
    )

    assert result["applied"] is False
    assert result["truncate_tables"] == ["framework_file_items"]
    assert fake_db.executed == []
    assert (runtime_dir / "file.txt").read_text(encoding="utf-8") == "keep"
    assert result["archived_dirs"] == []
    assert result["cleared_dirs"] == []


def test_clean_files_apply_requires_backup_dir(fake_db: FakeConnection, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="--backup-dir is required"):
        run_reset(
            apply=True,
            scope="files",
            clean_files=True,
            backup_dir=None,
            db_backup=make_db_backup(tmp_path),
            confirm="RESET huashiwangzu_v2",
        )
    assert fake_db.executed == []


def test_backup_dir_inside_runtime_dir_rejected(
    fake_db: FakeConnection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "backend" / "data"
    runtime_dir = data_dir / "uploads"
    backup_dir = runtime_dir / "backup"
    backup_dir.mkdir(parents=True)
    monkeypatch.setattr(reset_script, "BACKEND_DATA_DIR", data_dir)
    monkeypatch.setattr(reset_script, "RUNTIME_DIRS", [runtime_dir])

    with pytest.raises(SystemExit, match="must not be inside"):
        run_reset(
            apply=True,
            scope="files",
            clean_files=True,
            backup_dir=backup_dir,
            db_backup=make_db_backup(tmp_path),
            confirm="RESET huashiwangzu_v2",
        )
    assert fake_db.executed == []


def test_runtime_symlink_rejected(
    fake_db: FakeConnection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "backend" / "data"
    target_dir = tmp_path / "target"
    data_dir.mkdir(parents=True)
    target_dir.mkdir()
    symlink_dir = data_dir / "uploads"
    symlink_dir.symlink_to(target_dir, target_is_directory=True)
    monkeypatch.setattr(reset_script, "BACKEND_DATA_DIR", data_dir)
    monkeypatch.setattr(reset_script, "RUNTIME_DIRS", [symlink_dir])

    with pytest.raises(SystemExit, match="symlink"):
        run_reset(
            apply=True,
            scope="files",
            clean_files=True,
            backup_dir=tmp_path / "archive",
            db_backup=make_db_backup(tmp_path),
            confirm="RESET huashiwangzu_v2",
        )
    assert fake_db.executed == []


def test_db_backup_missing_rejected(fake_db: FakeConnection, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="--db-backup"):
        run_reset(
            apply=True,
            scope="tasks",
            clean_files=False,
            backup_dir=None,
            db_backup=tmp_path / "missing.sql",
            confirm="RESET huashiwangzu_v2",
        )
    assert fake_db.executed == []
