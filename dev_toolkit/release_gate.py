"""Release gate — pre-publish validation matrix.

Aggregates:
  1. /api/health
  2. /api/system/status
  3. smoke_all(default includes UI; --skip-ui marks backend coverage debt)
  4. Task queue audit (gate-run additions vs historical debt)
  5. Module sandbox matrix summary

Output levels:
  - PASS       everything green
  - BLOCKER    must fix before release (gate-run failures, health non-ok, worker down)
  - DEBT       known historical issues, tracked not blocking
  - SKIPPED_WITH_REASON  intentionally skipped (e.g. no sandbox test)

Usage:
    cd <repo> && backend/.venv/bin/python dev_toolkit/release_gate.py [--skip-ui] [--preflight]
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

try:
    from dev_toolkit.config_loader import load_config
    from dev_toolkit.process_tools import create_subprocess_exec_group, terminate_process_tree
    from dev_toolkit.release_gate_support import (
        _asset_marker_predicate as _asset_marker_predicate,
    )
    from dev_toolkit.release_gate_support import (
        _task_result_is_semantic_failure as _task_result_is_semantic_failure,
    )
    from dev_toolkit.release_gate_support import (
        audit_content_package_lifecycle_debt,
        audit_knowledge_lifecycle_debt,
        audit_test_data_pollution,
        classify_capability_drift,
        classify_component_key_contracts,
        classify_readme_acceptance_matrix,
        classify_sandbox_matrix,
        classify_semantic_failed_completed,
        ensure_envelope_success,
        find_semantic_failed_completed_tasks,
        parse_prefixed_json,
    )
    from dev_toolkit.release_gate_support import (
        scan_manifest_public_actions as scan_manifest_public_actions,
    )
    from dev_toolkit.release_gate_support import (
        scan_source_registered_capabilities as scan_source_registered_capabilities,
    )
    from dev_toolkit.release_gate_support import (
        semantic_failure_reason as semantic_failure_reason,
    )
except ModuleNotFoundError:
    from config_loader import load_config
    from process_tools import create_subprocess_exec_group, terminate_process_tree
    from release_gate_support import (
        _asset_marker_predicate as _asset_marker_predicate,
    )
    from release_gate_support import (
        _task_result_is_semantic_failure as _task_result_is_semantic_failure,
    )
    from release_gate_support import (
        audit_content_package_lifecycle_debt,
        audit_knowledge_lifecycle_debt,
        audit_test_data_pollution,
        classify_capability_drift,
        classify_component_key_contracts,
        classify_readme_acceptance_matrix,
        classify_sandbox_matrix,
        classify_semantic_failed_completed,
        ensure_envelope_success,
        find_semantic_failed_completed_tasks,
        parse_prefixed_json,
    )
    from release_gate_support import (
        scan_manifest_public_actions as scan_manifest_public_actions,
    )
    from release_gate_support import (
        scan_source_registered_capabilities as scan_source_registered_capabilities,
    )
    from release_gate_support import (
        semantic_failure_reason as semantic_failure_reason,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = REPO_ROOT / "modules"
BACKEND_PYTHON = REPO_ROOT / "backend" / ".venv" / "bin" / "python"
CONFIG = load_config(REPO_ROOT)
BACKEND_BASE = str(CONFIG.get("backend_base_url") or "http://127.0.0.1:33000")
FRONTEND_BASE = str(CONFIG.get("frontend_base_url") or "http://127.0.0.1:5173")
SEMANTIC_COMPLETED_SCAN_LIMIT = 500

DB_DSN = CONFIG.get("db_dsn", "")
ACCOUNTS = CONFIG.get("accounts", {})
RELEASE_GATE_CONFIG = CONFIG.get("release_gate", {})

results: list[dict[str, Any]] = []
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_MAX_AGE = 300  # 5 min — short enough to avoid stale-after-smoke expiry
runtime_context: dict[str, Any] = {}


def _project_python() -> str:
    return str(BACKEND_PYTHON if BACKEND_PYTHON.exists() else Path(sys.executable))


def add_result(check: str, level: str, detail: str, data: dict[str, Any] | None = None) -> None:
    item = {"check": check, "level": level, "detail": detail}
    if data is not None:
        item["data"] = data
    results.append(item)
    icon = {"PASS": "✅", "BLOCKER": "🔴", "DEBT": "🟡", "SKIPPED_WITH_REASON": "⏭️"}.get(level, "❓")
    print(f"  {icon} [{level:>20}] {check}: {detail[:200]}")


def _run_git(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def git_snapshot() -> dict[str, Any]:
    status_lines = [line for line in _run_git(["status", "--short"]).splitlines() if line.strip()]
    return {
        "sha": _run_git(["rev-parse", "HEAD"]),
        "short_sha": _run_git(["rev-parse", "--short", "HEAD"]),
        "branch": _run_git(["branch", "--show-current"]),
        "dirty": bool(status_lines),
        "dirty_count": len(status_lines),
        "dirty_files": status_lines[:80],
    }


def changed_module_keys(status_lines: list[str] | None = None) -> set[str]:
    lines = status_lines
    if lines is None:
        lines = [line for line in _run_git(["status", "--short"]).splitlines() if line.strip()]
    changed: set[str] = set()
    for line in lines:
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            continue
        match = re.match(r"modules/([^/]+)/", path)
        if match and not match.group(1).startswith("_"):
            changed.add(match.group(1))
    return changed


async def _url_status(base_url: str, path: str = "/") -> dict[str, Any]:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5, trust_env=False) as client:
            resp = await client.get(path)
        return {
            "available": resp.status_code < 500,
            "status_code": resp.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }


async def collect_runtime_context() -> None:
    runtime_context.clear()
    runtime_context.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_base_url": BACKEND_BASE,
        "frontend_base_url": FRONTEND_BASE,
        "git": git_snapshot(),
        "services": {
            "backend": await _url_status(BACKEND_BASE, "/api/health"),
            "frontend": await _url_status(FRONTEND_BASE, "/"),
        },
    })


async def _ensure_token(*, force_refresh: bool = False) -> str:
    now = time.monotonic()
    if not force_refresh and "admin" in _token_cache:
        cached_token, cached_at = _token_cache["admin"]
        if now - cached_at < _TOKEN_MAX_AGE:
            return cached_token
    acct = ACCOUNTS["admin"]
    if not acct.get("username") or not acct.get("password"):
        raise RuntimeError(
            "dev_toolkit admin account is not configured; set dev_toolkit/config.local.json "
            "or DEV_TOOLKIT_ADMIN_USERNAME/DEV_TOOLKIT_ADMIN_PASSWORD"
        )
    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=10, trust_env=False) as client:
        resp = await client.post("/api/login", json={
            "username": acct["username"],
            "password": acct["password"],
        })
        data = resp.json()
        token = data.get("data", {}).get("access_token") or data.get("access_token")
        if not token:
            raise RuntimeError(f"Login failed: {data}")
        _token_cache["admin"] = (token, now)
        return token


async def probe(method: str, path: str, body: dict | None = None) -> dict:
    token = await _ensure_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=30, trust_env=False) as client:
        resp = await client.request(method, path, json=body, headers=headers)
        if resp.status_code == 401:
            token = await _ensure_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, path, json=body, headers=headers)
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:500]}
        if not 200 <= resp.status_code < 300:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}",
                "status_code": resp.status_code,
                "data": payload,
            }
        return payload


async def fetch_task_queue_audit() -> dict[str, Any]:
    r = await probe("GET", "/api/tasks/worker/audit")
    ensure_envelope_success(r, "task queue audit")
    if not isinstance(r, dict):
        raise TypeError(f"unexpected response type: {type(r)}")
    d = r
    while isinstance(d, dict) and isinstance(d.get("data"), dict) and "summary" not in d:
        d = d["data"]
    if not isinstance(d, dict):
        raise TypeError(f"unexpected audit payload type: {type(d)}")
    return d


def audit_failed_count(audit: dict[str, Any]) -> int:
    summary = audit.get("summary", {})
    if not isinstance(summary, dict) or "failed" not in summary:
        raise ValueError("task queue audit missing summary.failed")
    value = summary.get("failed")
    return int(value or 0)


async def fetch_live_capabilities() -> list[dict[str, Any]]:
    payload = await probe("GET", "/api/modules/capabilities")
    ensure_envelope_success(payload, "module capabilities")
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        raise TypeError("module capabilities payload is not a list")
    return [item for item in data if isinstance(item, dict)]


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
        if backend_ok and db_ok and worker_ok:
            add_result("System status", "PASS", "backend/db/worker all ok")
        else:
            failing = [k for k in ("backend", "database", "worker") if not d.get(k, {}).get("status")]
            add_result("System status", "BLOCKER", f"failing: {', '.join(failing)}")
        runtime_context["system_status"] = d
    except Exception as e:
        add_result("System status", "BLOCKER", str(e))


async def check_smoke(skip_ui: bool) -> None:
    proc: asyncio.subprocess.Process | None = None
    try:
        started = time.monotonic()
        env_override = {"SMOKE_SKIP_UI": "1"} if skip_ui else {}
        env = {**os.environ.copy(), **env_override}
        proc = await create_subprocess_exec_group(
            _project_python(),
            str(REPO_ROOT / "dev_toolkit" / "smoke.py"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=REPO_ROOT,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=360)
        elapsed = time.monotonic() - started
        output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        passed = proc.returncode == 0
        smoke_summary = parse_prefixed_json(output, "SMOKE_JSON:")

        if smoke_summary:
            runtime_context["smoke"] = {
                "summary": smoke_summary,
                "returncode": proc.returncode,
                "duration_seconds": round(elapsed, 3),
                "skip_ui": skip_ui,
            }
            verdict = smoke_summary.get("verdict")
            counts = smoke_summary.get("counts", {})
            failed = int(counts.get("failed", 0) or 0) if isinstance(counts, dict) else 0
            skipped = int(counts.get("skipped", 0) or 0) if isinstance(counts, dict) else 0
            skipped_scenarios = smoke_summary.get("skipped_scenarios", [])
            if not passed or verdict == "FAIL":
                add_result("Smoke test (backends)", "BLOCKER",
                           f"{elapsed:.0f}s, exit={proc.returncode}, failed={failed}")
            elif verdict == "PASS_WITH_DEBT":
                names = ", ".join(str(item) for item in skipped_scenarios[:3])
                add_result("Smoke test (backends)", "DEBT",
                           f"{elapsed:.0f}s, passed with debt; skipped={skipped} ({names})")
            elif verdict == "PASS":
                add_result("Smoke test (backends)", "PASS",
                           f"{elapsed:.0f}s, clean pass")
            else:
                add_result("Smoke test (backends)", "BLOCKER",
                           f"{elapsed:.0f}s, unknown smoke verdict={verdict!r}")
            check_ui_smoke_summary(smoke_summary, skip_ui=skip_ui)
            check_model_fallback_summary(smoke_summary)
            return

        if passed:
            add_result("Smoke test (backends)", "BLOCKER",
                       f"{elapsed:.0f}s, missing SMOKE_JSON machine summary")
        else:
            # Extract failure count from output
            fail_lines = [line for line in output.splitlines() if "R]" in line or "❌" in line or "[R]" in line]
            add_result("Smoke test (backends)", "BLOCKER",
                       f"{elapsed:.0f}s, exit={proc.returncode}, failures: {len(fail_lines)}")
    except asyncio.TimeoutError:
        if proc is not None:
            await terminate_process_tree(proc)
        add_result("Smoke test (backends)", "BLOCKER", "timeout (>360s)")
    except asyncio.CancelledError:
        if proc is not None:
            await terminate_process_tree(proc)
        raise
    except Exception as e:
        add_result("Smoke test (backends)", "BLOCKER", str(e))


def check_ui_coverage(skip_ui: bool) -> None:
    if skip_ui:
        runtime_context["ui_coverage"] = {
            "status": "DEBT",
            "included": False,
            "reason": "--skip-ui used",
        }
        add_result(
            "UI coverage",
            "DEBT",
            "--skip-ui used; backend preflight only, not a clean release gate",
        )
        return
    runtime_context["ui_coverage"] = {
        "status": "PENDING",
        "included": True,
        "reason": "waiting for smoke Playwright summary",
    }
    add_result("UI coverage", "PASS", "UI smoke coverage included")


def check_ui_smoke_summary(smoke_summary: dict[str, Any], *, skip_ui: bool) -> None:
    if skip_ui:
        return
    ui_summary = smoke_summary.get("ui")
    if not isinstance(ui_summary, dict):
        runtime_context["ui_coverage"] = {
            "status": "BLOCKER",
            "included": True,
            "reason": "smoke summary missing ui field",
        }
        add_result("UI Playwright summary", "BLOCKER", "smoke summary missing UI machine summary")
        return

    failed = int(ui_summary.get("failed") or 0)
    passed = int(ui_summary.get("passed") or 0)
    skipped = int(ui_summary.get("skipped") or 0)
    status = str(ui_summary.get("status") or "")
    failed_tests = ui_summary.get("failed_tests") if isinstance(ui_summary.get("failed_tests"), list) else []
    artifacts = ui_summary.get("artifact_paths") if isinstance(ui_summary.get("artifact_paths"), list) else []
    runtime_context["ui_coverage"] = {
        "status": "PASS" if status == "pass" and failed == 0 else ("DEBT" if status == "unavailable" else "BLOCKER"),
        "included": True,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failed_tests": failed_tests[:10],
        "artifact_paths": artifacts[:20],
        "duration_seconds": ui_summary.get("duration_seconds"),
    }
    if status == "pass" and failed == 0:
        add_result("UI Playwright summary", "PASS", f"passed={passed}, skipped={skipped}, artifacts={len(artifacts)}")
    elif status == "unavailable":
        add_result("UI Playwright summary", "DEBT", str(ui_summary.get("reason") or "UI environment unavailable"))
    else:
        names = ", ".join(str(item.get("title", "?")) for item in failed_tests[:3] if isinstance(item, dict))
        add_result(
            "UI Playwright summary",
            "BLOCKER",
            f"failed={failed}, passed={passed}, artifacts={len(artifacts)}" + (f"; tests={names}" if names else ""),
        )


def check_model_fallback_summary(smoke_summary: dict[str, Any]) -> None:
    model_summary = smoke_summary.get("model_fallback")
    if not isinstance(model_summary, dict):
        runtime_context["model_fallback"] = {
            "status": "DEBT",
            "reason": "smoke summary missing model_fallback field",
        }
        add_result("Model fallback", "DEBT", "smoke summary missing model fallback summary")
        return

    status = str(model_summary.get("status") or "PASS")
    if status not in {"PASS", "DEBT", "BLOCKER"}:
        runtime_context["model_fallback"] = {
            "status": "BLOCKER",
            "reason": f"unknown model fallback status={status!r}",
        }
        add_result("Model fallback", "BLOCKER", f"unknown model fallback status={status!r}")
        return
    observations = model_summary.get("observations") if isinstance(model_summary.get("observations"), list) else []
    runtime_context["model_fallback"] = {
        "status": status,
        "fallback_used_count": int(model_summary.get("fallback_used_count") or 0),
        "blocker_count": int(model_summary.get("blocker_count") or 0),
        "observations": observations[:10],
    }
    if status == "BLOCKER":
        add_result("Model fallback", "BLOCKER", f"{runtime_context['model_fallback']['blocker_count']} model fallback blocker(s)")
    elif status == "DEBT":
        sample = observations[0] if observations and isinstance(observations[0], dict) else {}
        detail = str(sample.get("summary") or f"{model_summary.get('fallback_used_count', 0)} fallback debt observation(s)")
        add_result("Model fallback", "DEBT", detail)
    else:
        add_result("Model fallback", "PASS", "no blocking model fallback debt observed")


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
        gate_failed_delta = None if baseline_failed is None else max(0, int(failed or 0) - baseline_failed)
        historical_debt = d.get("historical_debt_total", 0)
        stale_pending = classification.get("stale_pending_debt_count", 0)
        orphan_running = classification.get("orphan_running_debt_count", 0)

        add_result("Queue: total", "PASS" if failed == 0 else "DEBT",
                   f"failed={failed}, pending={pending}, completed={summary.get('completed', 0)}")

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
                       f"failed increased during gate: {baseline_failed} -> {failed} (+{gate_failed_delta})")
        else:
            add_result("Queue: gate-run failed delta", "PASS",
                       f"no failed tasks added during gate: baseline={baseline_failed}, current={failed}")

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
                "DEBT",
                f"{obsolete_failed} of {recent_failed_total} recent failed task(s) are deleted-source obsolete debt",
            )
        else:
            add_result("Queue: deleted-source obsolete failures", "PASS", "no deleted-source obsolete failed tasks")

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
            entries = json.loads(output)
        except json.JSONDecodeError:
            add_result("Sandbox matrix", "DEBT",
                       f"bad JSON output (len={len(output)}), see stderr")
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


def get_final_verdict() -> str:
    blockers = [r for r in results if r["level"] == "BLOCKER"]
    debts = [r for r in results if r["level"] in {"DEBT", "SKIPPED_WITH_REASON"}]
    if blockers:
        return "BLOCKED"
    if debts:
        return "PASS_WITH_DEBT"
    return "PASS"


def _compact_items(levels: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "check": str(item.get("check", "")),
            "level": str(item.get("level", "")),
            "detail": str(item.get("detail", ""))[:300],
        }
        for item in results
        if item.get("level") in levels
    ]


def build_release_summary(verdict: str, *, skip_ui: bool = False, preflight: bool = False) -> dict[str, Any]:
    levels: dict[str, int] = {}
    for result in results:
        level = result["level"]
        levels[level] = levels.get(level, 0) + 1
    blockers = _compact_items({"BLOCKER"})
    debts = _compact_items({"DEBT", "SKIPPED_WITH_REASON"})
    has_blockers = bool(blockers) or verdict in {"BLOCKED", "BLOCKER"}
    if has_blockers:
        summary_verdict = "BLOCKED"
    elif (skip_ui or preflight) and verdict == "PASS":
        summary_verdict = "PASS_WITH_DEBT"
    else:
        summary_verdict = verdict
    has_debt = (
        skip_ui
        or preflight
        or levels.get("DEBT", 0) > 0
        or levels.get("SKIPPED_WITH_REASON", 0) > 0
    )
    clean_pass = summary_verdict == "PASS" and not skip_ui and not preflight and not has_debt and not has_blockers
    clean_release_ready = clean_pass and not has_debt
    release_safe = summary_verdict in {"PASS", "PASS_WITH_DEBT"} and not has_blockers
    deploy_allowed = release_safe
    ui_coverage_status = runtime_context.get("ui_coverage", {})
    model_fallback_status = runtime_context.get("model_fallback", {})
    compact_summary = {
        "verdict": summary_verdict,
        "blockers": blockers,
        "debts": debts,
        "release_safe": release_safe,
        "clean_release_ready": clean_release_ready,
        "deploy_allowed": deploy_allowed,
        "ui_coverage_status": ui_coverage_status,
        "model_fallback_status": model_fallback_status,
    }
    return {
        "verdict": summary_verdict,
        "blockers": blockers,
        "debts": debts,
        "compact_summary": compact_summary,
        "clean_pass": clean_pass,
        "clean_release_ready": clean_release_ready,
        "release_safe": release_safe,
        "deploy_allowed": deploy_allowed,
        "ui_coverage_status": ui_coverage_status,
        "model_fallback_status": model_fallback_status,
        "has_debt": has_debt,
        "ui_skipped": skip_ui,
        "preflight": preflight,
        "gate_mode": "preflight" if preflight else ("backend_preflight" if skip_ui else "full_release"),
        "context": runtime_context,
        "levels": levels,
        "results": results,
    }


async def main():
    parser = argparse.ArgumentParser(description="Release gate validation")
    parser.add_argument("--skip-ui", action="store_true",
                        help="Skip Playwright UI tests in smoke_all")
    parser.add_argument("--preflight", action="store_true",
                        help="Run fast health/status/queue checks only; skip smoke and sandbox matrix")
    parser.add_argument("--sandbox-jobs", type=int, default=int(RELEASE_GATE_CONFIG.get("sandbox_jobs", 1) or 1),
                        help="Pass-through concurrency for module_sandbox_matrix --jobs")
    parser.add_argument(
        "--sandbox-frontend-jobs",
        type=int,
        default=int(RELEASE_GATE_CONFIG.get("sandbox_frontend_jobs", 1) or 1),
        help="Pass-through concurrency for module_sandbox_matrix --frontend-jobs",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  RELEASE GATE")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Backend: {BACKEND_BASE}")
    print("=" * 70)

    await collect_runtime_context()
    git_info = runtime_context.get("git", {})
    if git_info.get("dirty"):
        add_result(
            "Git worktree",
            "DEBT",
            f"dirty files={git_info.get('dirty_count', 0)}; included in machine JSON",
        )
    else:
        add_result("Git worktree", "PASS", f"clean sha={git_info.get('short_sha', '')}")
    frontend_state = runtime_context.get("services", {}).get("frontend", {})
    add_result(
        "Frontend availability",
        "PASS" if frontend_state.get("available") else "DEBT",
        f"{FRONTEND_BASE} status={frontend_state.get('status_code', frontend_state.get('error', 'unknown'))}",
    )
    print()
    await check_health()
    print()
    await check_system_status()
    print()
    baseline_failed: int | None = None
    baseline_semantic_failed_completed: int | None = None
    try:
        baseline_failed = audit_failed_count(await fetch_task_queue_audit())
        add_result("Queue: pre-smoke baseline", "PASS", f"failed={baseline_failed}")
    except Exception as e:
        add_result("Queue: pre-smoke baseline", "BLOCKER", str(e))
    try:
        baseline_semantic_failed_completed, _ = find_semantic_failed_completed_tasks()
        level = "DEBT" if baseline_semantic_failed_completed > 0 else "PASS"
        add_result(
            "Queue: pre-smoke semantic baseline",
            level,
            f"semantic_failed_completed={baseline_semantic_failed_completed}",
        )
    except Exception as e:
        add_result("Queue: pre-smoke semantic baseline", "BLOCKER", str(e))
    print()
    check_ui_coverage(skip_ui=args.skip_ui)
    print()
    if args.preflight:
        add_result("Smoke test (backends)", "DEBT", "--preflight used; smoke_all not run")
        runtime_context["ui_coverage"] = {
            "status": "DEBT",
            "included": False,
            "reason": "--preflight used; Playwright not run",
        }
        add_result("UI Playwright summary", "DEBT", "--preflight used; Playwright not run")
        runtime_context["model_fallback"] = {
            "status": "DEBT",
            "reason": "--preflight used; model fallback probe not run",
        }
        add_result("Model fallback", "DEBT", "--preflight used; model fallback probe not run")
    else:
        await check_smoke(skip_ui=args.skip_ui)
        _token_cache.clear()
    print()
    await check_task_queue_audit(baseline_failed, baseline_semantic_failed_completed)
    print()
    check_asset_lifecycle_debt()
    print()
    await check_capability_drift()
    print()
    check_readme_acceptance_matrix()
    print()
    check_component_key_contracts()
    print()
    if args.preflight:
        add_result("Sandbox matrix", "DEBT", "--preflight used; sandbox matrix not run")
    else:
        await check_sandbox_matrix(args.sandbox_jobs, args.sandbox_frontend_jobs)

    print()
    print("=" * 70)
    verdict = get_final_verdict()
    if args.preflight and verdict == "PASS":
        verdict = "PASS_WITH_DEBT"
    print(f"  RELEASE GATE VERDICT: {verdict}")
    print("=" * 70)
    print(
        "RELEASE_GATE_JSON: "
        + json.dumps(build_release_summary(verdict, skip_ui=args.skip_ui, preflight=args.preflight), ensure_ascii=False)
    )
    print()
    print(f"{'Check':<40} {'Level':>20}  Detail")
    print("-" * 100)
    for r in results:
        print(f"{r['check']:<40} {r['level']:>20}  {r['detail'][:120]}")

    print()
    if verdict == "BLOCKED":
        blockers = [r for r in results if r["level"] == "BLOCKER"]
        print(f"🔴 BLOCKERS ({len(blockers)}):")
        for b in blockers:
            print(f"  - {b['check']}: {b['detail'][:200]}")
        sys.exit(1)
    elif verdict == "PASS_WITH_DEBT":
        debts = [r for r in results if r["level"] in {"DEBT", "SKIPPED_WITH_REASON"}]
        print(f"🟡 DEBTS ({len(debts)}):")
        for d in debts:
            print(f"  - {d['check']}: {d['detail'][:200]}")
        print("✅ No BLOCKERs — release is safe with tracked debt.")
    else:
        print("✅ ALL CHECKS PASS — ready for release!")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--semantic-scan-json":
        scan_count, scan_samples = find_semantic_failed_completed_tasks(int(sys.argv[2]))
        print(json.dumps({"count": scan_count, "samples": scan_samples}, ensure_ascii=False))
        raise SystemExit(0)
    asyncio.run(main())
