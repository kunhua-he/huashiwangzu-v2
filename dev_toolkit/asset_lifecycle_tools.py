"""Asset lifecycle and test-data pollution audit tools."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

try:
    from dev_toolkit.config_loader import load_config
    from dev_toolkit.sql_guard import readonly_psql_env
except ModuleNotFoundError:
    from config_loader import load_config
    from sql_guard import readonly_psql_env

TOOL_NAMES = {"test_data_pollution_audit", "test_data_pollution_cleanup"}
TEST_MARKERS = (
    "smoke-",
    "e2e-",
    "recycle-",
    "pytest-",
    "test-upload-",
    "test-file-",
    "test-pollution-",
    "lifecycle-source-",
    "permanent-source-",
)
CONFIRM_CLEAN_TEST_DATA = "CLEAN_TEST_DATA"


def tool_definitions() -> list[Any]:
    from mcp.types import Tool

    return [
        Tool(
            name="test_data_pollution_audit",
            description="只读审计 smoke/e2e/recycle/pytest 和强 test-* 标记测试数据对文件、回收站、Knowledge、ContentPackage 的污染。",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "样本数量上限", "default": 20},
                },
            },
        ),
        Tool(
            name="test_data_pollution_cleanup",
            description="dry-run 或确认清理明确测试 marker 的污染数据；真实执行必须 confirm=CLEAN_TEST_DATA。",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": True},
                    "limit": {"type": "integer", "default": 100},
                    "confirm": {"type": "string", "default": ""},
                    "reason": {"type": "string", "default": ""},
                },
            },
        ),
    ]


def handles_tool(name: str) -> bool:
    return name in TOOL_NAMES


async def handle_tool(repo_root: Path, name: str, arguments: dict[str, Any]) -> str:
    if name == "test_data_pollution_audit":
        result = audit_test_data_pollution(repo_root, limit=int(arguments.get("limit", 20) or 20))
    elif name == "test_data_pollution_cleanup":
        result = cleanup_test_data_pollution(
            repo_root,
            dry_run=bool(arguments.get("dry_run", True)),
            limit=int(arguments.get("limit", 100) or 100),
            confirm=str(arguments.get("confirm", "") or ""),
            reason=str(arguments.get("reason", "") or ""),
        )
    else:
        raise ValueError(f"未知资产生命周期工具: {name}")
    return json.dumps(result, ensure_ascii=False, indent=2)


def audit_test_data_pollution(repo_root: Path, *, limit: int = 20) -> dict[str, Any]:
    payload = _run_json_sql(repo_root, _audit_sql(limit), readonly=True)
    payload["markers"] = list(TEST_MARKERS)
    payload["dry_run"] = True
    return payload


def cleanup_test_data_pollution(
    repo_root: Path,
    *,
    dry_run: bool = True,
    limit: int = 100,
    confirm: str = "",
    reason: str = "",
) -> dict[str, Any]:
    audit = audit_test_data_pollution(repo_root, limit=min(limit, 50))
    if dry_run:
        return {
            **audit,
            "action": "test_data_pollution_cleanup",
            "dry_run": True,
            "selected": min(int(audit.get("candidate_file_count") or 0), limit),
            "changed": 0,
            "requires_confirm": True,
            "confirm_token": CONFIRM_CLEAN_TEST_DATA,
            "reason": reason,
        }
    if confirm != CONFIRM_CLEAN_TEST_DATA:
        return {
            "success": False,
            "error": "confirm must be CLEAN_TEST_DATA to clean test data pollution",
            "dry_run": False,
            "requires_confirm": True,
            "confirm_token": CONFIRM_CLEAN_TEST_DATA,
        }
    result = _run_json_sql(repo_root, _cleanup_sql(limit), readonly=False)
    physical_result = _delete_upload_paths(
        repo_root,
        [str(path) for path in result.pop("candidate_storage_paths", []) if path],
    )
    return {
        "success": True,
        "action": "test_data_pollution_cleanup",
        "dry_run": False,
        "limit": limit,
        "reason": reason,
        **result,
        **physical_result,
    }


def _load_dsn(repo_root: Path) -> str:
    dsn = str(load_config(repo_root).get("db_dsn") or "")
    if not dsn:
        raise RuntimeError("dev_toolkit config missing db_dsn")
    return dsn


def _run_json_sql(repo_root: Path, sql: str, *, readonly: bool) -> dict[str, Any]:
    env = readonly_psql_env(os.environ) if readonly else os.environ.copy()
    proc = subprocess.run(
        ["psql", _load_dsn(repo_root), "-t", "-A", "-q", "-c", sql],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"psql failed: {detail[:500]}")
    text = proc.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def _marker_predicate(column: str) -> str:
    parts = [f"lower(coalesce({column}, '')) like '%{marker}%'" for marker in TEST_MARKERS]
    return "(" + " or ".join(parts) + ")"


def _upload_root(repo_root: Path) -> Path:
    env_upload_dir = os.environ.get("UPLOAD_DIR")
    if env_upload_dir:
        upload_dir = Path(env_upload_dir)
        return (upload_dir if upload_dir.is_absolute() else repo_root / "backend" / upload_dir).resolve()

    env_file = repo_root / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "UPLOAD_DIR" and value.strip():
                upload_dir = Path(value.strip().strip("\"'"))
                return (upload_dir if upload_dir.is_absolute() else repo_root / "backend" / upload_dir).resolve()

    backend_default = (repo_root / "backend" / "data" / "uploads").resolve()
    if backend_default.exists():
        return backend_default
    return (repo_root / "data" / "uploads").resolve()


def _delete_upload_paths(repo_root: Path, storage_paths: list[str]) -> dict[str, Any]:
    upload_root = _upload_root(repo_root)
    deleted = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for storage_path in storage_paths:
        if not storage_path or storage_path in seen:
            continue
        seen.add(storage_path)
        full_path = (upload_root / storage_path).resolve()
        if os.path.commonpath([str(upload_root), str(full_path)]) != str(upload_root):
            skipped += 1
            errors.append({"storage_path": storage_path, "error": "outside_upload_root"})
            continue
        if not full_path.exists():
            skipped += 1
            continue
        if not full_path.is_file():
            skipped += 1
            errors.append({"storage_path": storage_path, "error": "not_a_file"})
            continue
        try:
            full_path.unlink()
            deleted += 1
        except OSError as exc:
            skipped += 1
            errors.append({"storage_path": storage_path, "error": str(exc)})
    return {
        "physical_deleted_files": deleted,
        "physical_skipped_files": skipped,
        "physical_delete_errors": errors[:20],
    }


def _audit_sql(limit: int) -> str:
    file_marker = _marker_predicate("f.name")
    storage_marker = _marker_predicate("f.storage_path")
    doc_marker = _marker_predicate("d.filename")
    limit = max(1, min(limit, 200))
    return f"""
with marker_files as (
  select f.id, f.name, f.extension, f.deleted, f.storage_path
  from framework_file_items f
  where {file_marker} or {storage_marker}
),
marker_docs as (
  select d.id, d.file_id, d.filename, d.deleted
  from kb_documents d
  left join marker_files mf on mf.id = d.file_id
  where mf.id is not null or {doc_marker}
),
marker_packages as (
  select p.id, p.source_file_id, p.status, p.deleted
  from framework_content_packages p
  join marker_files mf on mf.id = p.source_file_id
),
candidate_files as (
  select id from marker_files order by id desc limit {limit}
)
select json_build_object(
  'active_test_files', (select count(*) from marker_files where deleted=false),
  'recycled_test_files', (select count(*) from marker_files where deleted=true),
  'knowledge_documents_from_test_files', (select count(*) from marker_docs where deleted=false),
  'content_packages_from_test_files', (select count(*) from marker_packages where deleted=false),
  'uploads_test_artifacts', (select count(*) from marker_files where storage_path is not null and storage_path <> ''),
  'candidate_file_count', (select count(*) from marker_files),
  'candidate_file_ids', coalesce((select json_agg(id) from candidate_files), '[]'::json),
  'sample_files', coalesce((
    select json_agg(json_build_object('id', id, 'name', name, 'extension', extension, 'deleted', deleted))
    from (select * from marker_files order by id desc limit {limit}) s
  ), '[]'::json)
)::text;
"""


def _cleanup_sql(limit: int) -> str:
    file_marker = _marker_predicate("f.name")
    storage_marker = _marker_predicate("f.storage_path")
    doc_marker = _marker_predicate("d.filename")
    limit = max(1, min(limit, 5000))
    return f"""
with candidate_files as (
  select f.id, f.storage_path, f.md5_hash
  from framework_file_items f
  where {file_marker} or {storage_marker}
  order by f.id desc
  limit {limit}
),
candidate_docs as (
  select d.id
  from kb_documents d
  left join candidate_files cf on cf.id = d.file_id
  where d.deleted = false
    and (cf.id is not null or {doc_marker})
  order by d.id desc
  limit {limit}
),
archived_docs as (
  update kb_documents
  set deleted = true, parse_error = coalesce(parse_error, 'archived_by_test_data_cleanup')
  where id in (select id from candidate_docs) and deleted = false
  returning id
),
archived_packages as (
  update framework_content_packages
  set status = 'archived',
      parse_error = 'archived_by_test_data_cleanup',
      manifest_json = jsonb_set(
        coalesce(nullif(manifest_json, '')::jsonb, '{{}}'::jsonb),
        '{{lifecycle}}',
        coalesce((coalesce(nullif(manifest_json, '')::jsonb, '{{}}'::jsonb)->'lifecycle'), '{{}}'::jsonb)
          || jsonb_build_object(
            'archived_by_lifecycle', true,
            'source_available', false,
            'source_lifecycle_state', 'source_permanently_deleted',
            'reason', 'archived_by_test_data_cleanup'
          ),
        true
      )::text
  where source_file_id in (select id from candidate_files) and deleted = false
  returning id
),
deleted_recycle as (
  delete from framework_file_recycle_items
  where item_type = 'file' and origin_id in (select id from candidate_files)
  returning id
),
deleted_files as (
  delete from framework_file_items
  where id in (select id from candidate_files)
  returning id
)
select json_build_object(
  'selected_files', (select count(*) from candidate_files),
  'candidate_storage_paths', coalesce((
    select json_agg(cf.storage_path)
    from candidate_files cf
    where cf.storage_path is not null
      and cf.storage_path <> ''
      and not exists (
        select 1
        from framework_file_items f
        where f.id not in (select id from candidate_files)
          and f.storage_path = cf.storage_path
      )
      and not exists (
        select 1
        from framework_file_items f
        where f.id not in (select id from candidate_files)
          and cf.md5_hash is not null
          and cf.md5_hash <> ''
          and f.md5_hash = cf.md5_hash
      )
  ), '[]'::json),
  'archived_documents', (select count(*) from archived_docs),
  'archived_packages', (select count(*) from archived_packages),
  'deleted_recycle_rows', (select count(*) from deleted_recycle),
  'deleted_file_rows', (select count(*) from deleted_files)
)::text;
"""
