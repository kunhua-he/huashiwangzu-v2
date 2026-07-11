"""Release gate checks that inspect the live system and repo contracts."""
from __future__ import annotations

import asyncio
import json
import os
import time

try:
    from dev_toolkit.contract_tools import capability_contract_diff
    from dev_toolkit.docs_sync import docs_audit
    from dev_toolkit.process_tools import create_subprocess_exec_group, terminate_process_tree
    from dev_toolkit.release_gate_support import (
        audit_content_package_lifecycle_debt,
        audit_file_share_schema,
        audit_knowledge_lifecycle_debt,
        audit_pgvector_access,
        audit_test_data_pollution,
        classify_capability_drift,
        classify_component_key_contracts,
        classify_readme_acceptance_matrix,
        classify_sandbox_matrix,
        classify_semantic_failed_completed,
        ensure_envelope_success,
        find_semantic_failed_completed_tasks,
        inspect_alembic_revision_state,
    )
except ModuleNotFoundError:
    from contract_tools import capability_contract_diff
    from docs_sync import docs_audit
    from process_tools import create_subprocess_exec_group, terminate_process_tree
    from release_gate_support import (
        audit_content_package_lifecycle_debt,
        audit_file_share_schema,
        audit_knowledge_lifecycle_debt,
        audit_pgvector_access,
        audit_test_data_pollution,
        classify_capability_drift,
        classify_component_key_contracts,
        classify_readme_acceptance_matrix,
        classify_sandbox_matrix,
        classify_semantic_failed_completed,
        ensure_envelope_success,
        find_semantic_failed_completed_tasks,
        inspect_alembic_revision_state,
    )

from .context import (
    REPO_ROOT,
    _ensure_token,
    _project_python,
    changed_module_keys,
    fetch_live_capabilities,
    fetch_task_queue_audit,
    probe,
    runtime_context,
)
from .printers import add_result


async def check_health() -> None:
    try:
        r = await probe("GET", "/api/health")
        ensure_envelope_success(r, "health")
        d = r.get("data", r)
        status = d.get("status", "unknown")
        if status == "ok":
            add_result("Health check", "PASS", f"status={status}, db={d.get('database')}")
        else:
            add_result("Health check", "BLOCKER", f"status={status}, db={d.get('database')}")
        runtime_context["health"] = d
    except Exception as e:
        add_result("Health check", "BLOCKER", str(e))

async def check_system_status() -> None:
    try:
        r = await probe("GET", "/api/system/status")
        ensure_envelope_success(r, "system status")
        d = r.get("data", r)
        backend_ok = d.get("backend", {}).get("status") is True
        db_ok = d.get("database", {}).get("status") is True
        worker_ok = d.get("worker", {}).get("status") is True
        model_ok = d.get("model_service", {}).get("status") is True
        entry_ok = d.get("entry", {}).get("status") is True
        require_entry = os.getenv("RELEASE_GATE_REQUIRE_ENTRY", "").strip().lower() in {"1", "true", "yes", "on"}
        if backend_ok and db_ok and worker_ok and model_ok and (entry_ok or not require_entry):
            detail = "backend/db/worker/model all ok"
            if not entry_ok:
                detail += "; entry not required in this environment"
            add_result("System status", "PASS" if entry_ok or not require_entry else "DEBT", detail)
        else:
            blocker_keys = ["backend", "database", "worker", "model_service"]
            failing = [k for k in blocker_keys if not d.get(k, {}).get("status")]
            if require_entry and not entry_ok:
                failing.append("entry")
            add_result("System status", "BLOCKER", f"failing: {', '.join(failing)}")
        runtime_context["system_status"] = d
    except Exception as e:
        add_result("System status", "BLOCKER", str(e))

def check_alembic_revision_state() -> None:
    try:
        data = inspect_alembic_revision_state()
        runtime_context["alembic_revision_state"] = data
        heads = data.get("heads", [])
        current_versions = data.get("current_versions", [])
        missing = data.get("missing_current_heads", [])
        extra = data.get("extra_current_versions", [])
        detail = (
            f"heads={heads}, current={current_versions}, "
            f"missing={missing}, extra={extra}"
        )
        if data.get("head_count") != 1:
            add_result("Alembic revision state", "BLOCKER", detail, data)
        elif missing:
            add_result("Alembic revision state", "BLOCKER", detail, data)
        elif extra:
            add_result("Alembic revision state", "DEBT", detail, data)
        else:
            add_result("Alembic revision state", "PASS", detail, data)
    except Exception as exc:
        add_result("Alembic revision state", "BLOCKER", str(exc))

def check_pgvector_access() -> None:
    try:
        data = audit_pgvector_access()
        runtime_context["pgvector_access"] = data
        available = data.get("available_default_version")
        installed = data.get("installed_version")
        distance = data.get("probe_distance")
        detail = f"available={available}, installed={installed}, probe_distance={distance}"
        if not available:
            add_result("pgvector access", "BLOCKER", detail, data)
        elif not installed:
            add_result("pgvector access", "BLOCKER", detail, data)
        elif float(distance) != 0.0:
            add_result("pgvector access", "BLOCKER", detail, data)
        else:
            add_result("pgvector access", "PASS", detail, data)
    except Exception as exc:
        add_result("pgvector access", "BLOCKER", str(exc))


def check_file_share_schema() -> None:
    try:
        data = audit_file_share_schema()
        runtime_context["file_share_schema"] = data
        missing = data.get("missing_columns", [])
        if missing:
            add_result("File share schema", "BLOCKER", f"missing columns={missing}", data)
        else:
            add_result("File share schema", "PASS", "required columns present", data)
    except Exception as exc:
        add_result("File share schema", "BLOCKER", str(exc))

async def check_auth_files_probe() -> None:
    try:
        await _ensure_token(force_refresh=True)
        payload = await probe("GET", "/api/files/list?page=1&page_size=20")
        ensure_envelope_success(payload, "files list")
        data = payload.get("data", payload)
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            add_result("Desktop files API", "PASS", f"items={len(items)}")
            downloadable = next((item for item in items if isinstance(item, dict) and not item.get("is_folder")), None)
            if downloadable is None:
                search_payload = await probe("GET", "/api/files/search?page=1&page_size=50")
                ensure_envelope_success(search_payload, "files search")
                search_data = search_payload.get("data", search_payload)
                search_items = search_data.get("items") if isinstance(search_data, dict) else None
                if isinstance(search_items, list):
                    downloadable = next(
                        (item for item in search_items if isinstance(item, dict) and not item.get("is_folder")),
                        None,
                    )
            if downloadable:
                download_payload = await probe("GET", f"/api/files/download/{downloadable['id']}")
                if isinstance(download_payload, dict) and download_payload.get("success") is False:
                    raise RuntimeError(download_payload.get("error") or "file download failed")
                add_result("Desktop file download API", "PASS", f"file_id={downloadable['id']}")
            else:
                add_result("Desktop file download API", "DEBT", "no downloadable file sample found")
        else:
            add_result("Desktop files API", "BLOCKER", "bad shape: data.items is not a list", payload)
    except Exception as exc:
        add_result("Desktop files API", "BLOCKER", str(exc))


async def check_runtime_drift() -> None:
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await create_subprocess_exec_group(
            "npm",
            "run",
            "check:runtime-drift",
            "--silent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=REPO_ROOT / "frontend",
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = "\n".join(
            part.strip()
            for part in (stdout.decode(errors="replace"), stderr.decode(errors="replace"))
            if part.strip()
        )
        if proc.returncode == 0:
            add_result("Runtime drift", "PASS", output.splitlines()[-1] if output else "OK")
        else:
            add_result("Runtime drift", "BLOCKER", output[:500] or f"exit={proc.returncode}")
    except asyncio.TimeoutError:
        if proc is not None:
            await terminate_process_tree(proc)
        add_result("Runtime drift", "BLOCKER", "timeout (>30s)")
    except Exception as exc:
        add_result("Runtime drift", "BLOCKER", str(exc))


async def check_task_queue_audit(
    baseline_failed: int | None,
    baseline_semantic_failed_completed: int | None = None,
) -> None:
    try:
        d = await fetch_task_queue_audit()
        summary = d.get("summary", {})
        classification = d.get("classification", {})
        stalest = d.get("stalest_pending")
        runtime_context["task_debt_summary"] = {
            "summary": summary,
            "classification": classification,
            "recent_failed_count": d.get("recent_failed_count", classification.get("recent_failed_count", 0)),
            "recent_failed_total_count": d.get(
                "recent_failed_total_count",
                classification.get("recent_failed_total_count", d.get("recent_failed_count", 0)),
            ),
            "deleted_source_obsolete_failed_count": classification.get("deleted_source_obsolete_failed_count", 0),
            "historical_debt_total": d.get("historical_debt_total", 0),
            "stalest_pending": stalest,
            "metadata": d.get("metadata", {}),
        }

        failed = summary.get("failed", 0)
        pending = summary.get("pending", 0)
        recent_failed = d.get("recent_failed_count", classification.get("recent_failed_count", 0))
        recent_failed_total = d.get("recent_failed_total_count", classification.get("recent_failed_total_count", recent_failed))
        obsolete_failed = classification.get("deleted_source_obsolete_failed_count", 0)
        active_failed = max(0, int(failed or 0) - int(obsolete_failed or 0))
        gate_failed_delta = None if baseline_failed is None else max(0, active_failed - baseline_failed)
        historical_debt = d.get("historical_debt_total", 0)
        paused_pending = classification.get("paused_pending_count", 0)
        stale_pending = classification.get("stale_pending_debt_count", 0)
        orphan_running = classification.get("orphan_running_debt_count", 0)

        add_result(
            "Queue: total",
            "PASS" if active_failed == 0 else "DEBT",
            (
                f"failed={failed}, active_failed={active_failed}, "
                f"deleted_source_obsolete={obsolete_failed}, pending={pending}, "
                f"completed={summary.get('completed', 0)}"
            ),
        )

        if historical_debt > 0:
            add_result("Queue: historical debt", "DEBT",
                       f"{historical_debt} failed tasks older than 1h")
        else:
            add_result("Queue: historical debt", "PASS", "no historical failed tasks")

        if gate_failed_delta is None:
            add_result("Queue: gate-run failed delta", "BLOCKER",
                       "missing pre-smoke failed baseline")
        elif gate_failed_delta > 0:
            add_result("Queue: gate-run failed delta", "BLOCKER",
                       f"active failed increased during gate: {baseline_failed} -> {active_failed} (+{gate_failed_delta})")
        else:
            add_result("Queue: gate-run failed delta", "PASS",
                       f"no active failed tasks added during gate: baseline={baseline_failed}, current={active_failed}")

        if recent_failed > 0:
            window_hours = d.get("metadata", {}).get("recent_failure_window_hours", "?")
            add_result("Queue: recent failed window", "DEBT",
                       f"{recent_failed} failed task(s) in the last {window_hours}h; tracked as debt unless gate delta grows")
        else:
            add_result("Queue: recent failed window", "PASS",
                       "no failed tasks in recent audit window")

        if obsolete_failed > 0:
            add_result(
                "Queue: deleted-source obsolete failures",
                "INFO",
                f"{obsolete_failed} of {recent_failed_total} recent failed task(s) are deleted-source obsolete; not active failure debt",
            )
        else:
            add_result("Queue: deleted-source obsolete failures", "PASS", "no deleted-source obsolete failed tasks")

        if paused_pending > 0:
            add_result(
                "Queue: paused pending",
                "PASS",
                f"{paused_pending} sampled pending task(s) are intentionally paused by worker config",
            )
        else:
            add_result("Queue: paused pending", "PASS", "no paused pending in audit sample")

        if stale_pending > 0:
            info = f"{stale_pending} stale pending (not new)"
            if stalest:
                info += f", oldest: type={stalest.get('task_type')} age={stalest.get('age_seconds')}s"
            add_result("Queue: stale pending", "DEBT",
                       info + " — not a BLOCKER because they predate current deploy")
        else:
            add_result("Queue: stale pending", "PASS", "no stale pending")

        if orphan_running > 0:
            add_result("Queue: orphan running", "DEBT",
                       f"{orphan_running} orphan running (not new)")
        else:
            add_result("Queue: orphan running", "PASS", "no orphan running")

        semantic_count, semantic_samples = find_semantic_failed_completed_tasks()
        semantic_level, semantic_detail = classify_semantic_failed_completed(
            semantic_count,
            baseline_semantic_failed_completed,
            semantic_samples,
        )
        add_result("Queue: semantic failed completed", semantic_level, semantic_detail)

    except Exception as e:
        add_result("Queue: audit", "BLOCKER", str(e))

def check_asset_lifecycle_debt() -> None:
    try:
        knowledge = audit_knowledge_lifecycle_debt()
        unavailable = int(knowledge.get("source_unavailable") or 0)
        level = "DEBT" if unavailable > 0 else "PASS"
        detail = (
            f"source_unavailable={unavailable}, source_recycled={knowledge.get('source_recycled', 0)}, "
            f"source_missing={knowledge.get('source_missing', 0)}"
        )
        runtime_context["knowledge_lifecycle_debt"] = knowledge
        add_result("Knowledge lifecycle debt", level, detail, knowledge)
    except Exception as exc:
        add_result("Knowledge lifecycle debt", "BLOCKER", str(exc))

    try:
        content = audit_content_package_lifecycle_debt()
        unavailable = int(content.get("source_unavailable") or 0)
        unarchived = int(content.get("unarchived_source_unavailable") or 0)
        missing_current = int(content.get("missing_current_version") or 0)
        if missing_current > 0:
            level = "BLOCKER"
        elif unarchived > 0:
            level = "DEBT"
        else:
            level = "PASS"
        detail = (
            f"source_unavailable={unavailable}, archived={content.get('archived_by_lifecycle', 0)}, "
            f"unarchived={unarchived}, missing_current_version={missing_current}"
        )
        runtime_context["content_package_lifecycle_debt"] = content
        add_result("ContentPackage lifecycle debt", level, detail, content)
    except Exception as exc:
        add_result("ContentPackage lifecycle debt", "BLOCKER", str(exc))

    try:
        pollution = audit_test_data_pollution()
        total = sum(
            int(pollution.get(key) or 0)
            for key in (
                "active_test_files",
                "recycled_test_files",
                "knowledge_documents_from_test_files",
                "content_packages_from_test_files",
            )
        )
        active = int(pollution.get("active_test_files") or 0)
        level = "BLOCKER" if total > 0 else "PASS"
        detail = (
            f"active={active}, recycled={pollution.get('recycled_test_files', 0)}, "
            f"knowledge={pollution.get('knowledge_documents_from_test_files', 0)}, "
            f"content={pollution.get('content_packages_from_test_files', 0)}"
        )
        runtime_context["test_data_pollution"] = pollution
        add_result("Test data pollution", level, detail, pollution)
    except Exception as exc:
        add_result("Test data pollution", "BLOCKER", str(exc))

async def check_capability_drift() -> None:
    try:
        live = await fetch_live_capabilities()
        level, detail, data = classify_capability_drift(live)
        runtime_context["capability_drift"] = data
        add_result("Capability drift", level, detail, data)
    except Exception as exc:
        add_result("Capability drift", "BLOCKER", str(exc))

    try:
        data = capability_contract_diff(REPO_ROOT, include_parameters=True)
        summary = data.get("summary", {})
        runtime_context["capability_contract_diff"] = data
        detail = (
            f"modules_with_drift={summary.get('modules_with_drift', 0)}, "
            f"uncheckable_sites={summary.get('uncheckable_sites', 0)}, "
            f"checked_modules={summary.get('checked_modules', 0)}"
        )
        add_result(
            "Capability metadata drift",
            "PASS" if data.get("success") else "BLOCKER",
            detail,
            data,
        )
    except Exception as exc:
        add_result("Capability metadata drift", "BLOCKER", str(exc))

def check_readme_acceptance_matrix() -> None:
    try:
        level, detail, data = classify_readme_acceptance_matrix(changed_modules=changed_module_keys())
        runtime_context["readme_acceptance_matrix"] = data
        add_result("README acceptance matrix", level, detail, data)
    except Exception as exc:
        add_result("README acceptance matrix", "BLOCKER", str(exc))

def check_component_key_contracts() -> None:
    try:
        level, detail, data = classify_component_key_contracts()
        runtime_context["component_key_contracts"] = data
        add_result("Component key contracts", level, detail, data)
    except Exception as exc:
        add_result("Component key contracts", "BLOCKER", str(exc))


def check_docs_currentness() -> None:
    try:
        data = docs_audit(REPO_ROOT)
        summary = data.get("summary", {})
        level = str(data.get("level") or "BLOCKER")
        detail = (
            f"blockers={summary.get('blockers', 0)}, "
            f"debts={summary.get('debts', 0)}, issues={summary.get('issues', 0)}"
        )
        runtime_context["docs_currentness"] = data
        add_result("Docs currentness", level, detail, data)
    except Exception as exc:
        add_result("Docs currentness", "BLOCKER", str(exc))

async def check_sandbox_matrix(sandbox_jobs: int = 1, frontend_jobs: int = 1) -> None:
    """Run module_sandbox_matrix.py and report summary."""
    proc: asyncio.subprocess.Process | None = None
    try:
        started = time.monotonic()
        proc = await create_subprocess_exec_group(
            _project_python(),
            str(REPO_ROOT / "dev_toolkit" / "module_sandbox_matrix.py"),
            "--check", "--json",
            "--jobs", str(max(1, sandbox_jobs)),
            "--frontend-jobs", str(max(1, frontend_jobs)),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=REPO_ROOT,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        elapsed = time.monotonic() - started
        output = stdout.decode(errors="replace")

        if proc.returncode != 0 and proc.returncode != 1:
            add_result("Sandbox matrix", "BLOCKER",
                       f"script crashed (exit={proc.returncode})")
            return

        try:
            matrix_payload = json.loads(output)
        except json.JSONDecodeError:
            add_result("Sandbox matrix", "DEBT",
                       f"bad JSON output (len={len(output)}), see stderr")
            return
        entries = matrix_payload.get("entries") if isinstance(matrix_payload, dict) else matrix_payload
        if not isinstance(entries, list):
            add_result("Sandbox matrix", "BLOCKER", "bad JSON shape: expected entries list")
            return

        level, detail = classify_sandbox_matrix(entries, elapsed)
        chunk_warning_modules = [
            str(e.get("module"))
            for e in entries
            if e.get("chunk_warnings")
            or any(result.get("chunk_warnings") for result in e.get("command_results", []) if isinstance(result, dict))
        ]
        runtime_context["sandbox_matrix"] = {
            "total": len(entries),
            "passed": sum(1 for e in entries if e.get("check") == "pass"),
            "failed": sum(1 for e in entries if e.get("check") == "fail"),
            "skipped": sum(1 for e in entries if e.get("check") == "skip"),
            "chunk_warning_count": len(chunk_warning_modules),
            "chunk_warning_modules": chunk_warning_modules[:10],
            "duration_seconds": round(elapsed, 3),
            "jobs": sandbox_jobs,
            "frontend_jobs": frontend_jobs,
        }
        add_result("Sandbox matrix", level, detail)
    except asyncio.TimeoutError:
        if proc is not None:
            await terminate_process_tree(proc)
        add_result("Sandbox matrix", "BLOCKER", "timeout (>180s)")
    except asyncio.CancelledError:
        if proc is not None:
            await terminate_process_tree(proc)
        raise
    except Exception as e:
        add_result("Sandbox matrix", "BLOCKER", str(e))
