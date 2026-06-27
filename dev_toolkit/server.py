"""
项目工具台 MCP Server
自包含 MCP 服务器, stdio 传输, 暴露 15 个开发工具.
"""

import asyncio
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

try:
    from dev_toolkit.quick_fix import QuickFixError, quick_fix_patch, quick_fix_preview
except ModuleNotFoundError:
    from quick_fix import QuickFixError, quick_fix_patch, quick_fix_preview

# ── 配置 ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "dev_toolkit" / "config.json"

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

BACKEND_BASE = CONFIG["backend_base_url"]
BGE_M3_URL = CONFIG["bge_m3_url"]
ACCOUNTS = CONFIG["accounts"]
MEMORY_DIR = REPO_ROOT / CONFIG["memory_dir"]
EMBEDDING_CACHE_PATH = REPO_ROOT / CONFIG["embedding_cache"]
LOG_DIR = REPO_ROOT / CONFIG["log_dir"]
DB_DSN = CONFIG["db_dsn"]
UPLOADS_DIR = REPO_ROOT / "backend" / "data" / "uploads"
_OUTPUT_TAIL_LIMIT = 8000
MEMORY_NOISE_PATTERN = re.compile(
    r"(e2e-|smoke-|test-|test_|kb_test|kb-test|ui-e2e|audit-test|renamed-audit-test|docs-open验收|event_test|e2e_test|sample|to_del|验收|smoke)",
    re.IGNORECASE,
)


def _is_knowledge_noise_name(filename: str) -> bool:
    """Check if a filename looks like a test/smoke/validation artifact."""
    return bool(MEMORY_NOISE_PATTERN.search(filename))


# ── 通用 helper ───────────────────────────────────────────────────────


def _tail_text(text: str, limit: int = _OUTPUT_TAIL_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _resolve_repo_path(path: str, *, base_dir: Path | None = None) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        base = base_dir or REPO_ROOT
        resolved = (base / raw).resolve()
    if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
        raise ValueError(f"路径必须在仓库内: {path}")
    return resolved


def _normalize_pytest_targets(target: str) -> list[str]:
    backend_dir = REPO_ROOT / "backend"
    normalized: list[str] = []
    for raw_part in shlex.split(target):
        path_part, sep, suffix = raw_part.partition("::")
        if not path_part:
            continue
        try:
            resolved = _resolve_repo_path(path_part, base_dir=backend_dir)
        except ValueError:
            normalized.append(raw_part)
            continue
        if resolved.exists():
            try:
                rel = resolved.relative_to(backend_dir)
                normalized.append(str(rel) + (sep + suffix if sep else ""))
                continue
            except ValueError:
                normalized.append(str(resolved) + (sep + suffix if sep else ""))
                continue
        if path_part.startswith("backend/"):
            normalized.append(path_part.removeprefix("backend/") + (sep + suffix if sep else ""))
        else:
            normalized.append(raw_part)
    return normalized


async def _run_command_json(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    started = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return {
            "success": False,
            "timeout": True,
            "timeout_seconds": timeout,
            "command": cmd,
            "cwd": str(cwd),
            "duration_seconds": round(time.time() - started, 3),
            "stdout": "",
            "stderr": "",
        }
    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    return {
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": cmd,
        "cwd": str(cwd),
        "duration_seconds": round(time.time() - started, 3),
        "stdout": out,
        "stderr": err,
        "stdout_tail": _tail_text(out),
        "stderr_tail": _tail_text(err),
    }


async def _git_status_summary() -> dict[str, Any]:
    result = await _run_command_json(
        ["git", "status", "--short", "--branch"],
        cwd=REPO_ROOT,
        timeout=10,
    )
    lines = [line for line in result.get("stdout", "").splitlines() if line.strip()]
    branch = lines[0].removeprefix("## ") if lines else ""
    changed = lines[1:]
    return {
        "branch": branch,
        "is_main": branch.split("...")[0] in {"main", "master"},
        "dirty_count": len(changed),
        "sample": changed[:25],
    }


# 确保记忆目录存在
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
EMBEDDING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Token 缓存 ────────────────────────────────────────────────────────

_token_cache: dict[str, dict[str, Any]] = {}  # role -> {"token": str, "expires_at": float}

async def _ensure_token(role: str = "admin", *, force_refresh: bool = False) -> str:
    if role not in ACCOUNTS:
        role = "admin"
    now = time.time()
    cached = _token_cache.get(role)
    if not force_refresh and cached and cached["expires_at"] > now + 60:
        return cached["token"]
    acct = ACCOUNTS[role]
    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=10) as client:
        resp = await client.post("/api/login", json={
            "username": acct["username"],
            "password": acct["password"],
        })
        data = resp.json()
        token = data.get("data", data).get("access_token") or data.get("access_token")
        if not token:
            raise RuntimeError(f"登录失败 {role}: {data}")
        _token_cache[role] = {"token": token, "expires_at": now + 3600}
        return token


async def _ensure_live_token(role: str = "admin") -> str:
    token = await _ensure_token(role, force_refresh=True)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=10) as client:
        resp = await client.get("/api/current-user", headers=headers)
        if resp.status_code == 200:
            return token
    token = await _ensure_token(role, force_refresh=True)
    _token_cache.pop(role, None)
    return token

# ── 嵌入服务 ──────────────────────────────────────────────────────────

async def _get_embedding(text: str) -> list[float] | None:
    # v2 的 bge-m3 是 llama-server(端口30000), OpenAI 兼容 /v1/embeddings
    try:
        async with httpx.AsyncClient(base_url=BGE_M3_URL, timeout=10) as client:
            resp = await client.post("/v1/embeddings", json={"input": text, "model": "bge-m3"})
            if resp.status_code == 200:
                data = resp.json()
                emb = (data.get("data") or [{}])[0].get("embedding")
                if emb:
                    return emb
    except Exception:
        pass
    return None

def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0

def _load_embedding_cache() -> dict[str, list[float]]:
    if EMBEDDING_CACHE_PATH.exists():
        return json.loads(EMBEDDING_CACHE_PATH.read_text(encoding="utf-8"))
    return {}

def _save_embedding_cache(cache: dict[str, list[float]]) -> None:
    tmp = EMBEDDING_CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.rename(EMBEDDING_CACHE_PATH)

# ── 记忆文件操作 ─────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    s = s.strip("-")
    return s or "memory"

def _list_memories() -> list[dict]:
    """Return all memories sorted by created desc."""
    memories = []
    for f in sorted(MEMORY_DIR.iterdir()):
        if f.suffix != ".md" or f.stem.startswith("_"):
            continue
        content = f.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        fm["slug"] = f.stem
        fm["path"] = str(f.relative_to(REPO_ROOT))
        memories.append(fm)
    memories.sort(key=lambda m: m.get("created", ""), reverse=True)
    return memories

def _parse_frontmatter(content: str) -> dict:
    """Parse YAML-like frontmatter from markdown."""
    meta: dict[str, Any] = {"name": "", "type": "reference", "tags": [], "created": "", "body": content}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if m:
        body = m.group(2).strip()
        meta["body"] = body
        for line in m.group(1).split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if key == "tags":
                    meta["tags"] = [t.strip().strip('"').strip("'") for t in val.strip("[]").split(",") if t.strip()]
                elif key in ("name", "type", "created", "agent"):
                    meta[key] = val.strip('"').strip("'")
    return meta

def _update_index() -> None:
    index_path = MEMORY_DIR / "_索引.md"
    lines = ["# 项目记忆索引\n", "\n", "每条记忆一条记录:\n", "- `[slug](slug.md)` — type — tags — created\n", "\n", "---\n", "\n"]
    for m in _list_memories():
        tag_str = ", ".join(m.get("tags", []))
        lines.append(f"- `[{m['slug']}]({m['slug']}.md)` — {m.get('type','')} — [{tag_str}] — {m.get('created','')}\n")
    tmp = index_path.with_suffix(".md.tmp")
    Path(tmp).write_text("".join(lines), encoding="utf-8")
    Path(tmp).rename(index_path)

# ── SQL 只读执行器 ──────────────────────────────────────────────────

# 允许的 SQL 语句前缀
_ALLOWED_PREFIXES = ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE")
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|EXECUTE|CALL|MERGE)\b",
    re.IGNORECASE,
)

def _check_sql_readonly(query: str) -> None:
    stripped = query.strip().lstrip("(")
    upper = stripped.upper()
    if not upper.startswith(_ALLOWED_PREFIXES):
        # 允许以 WITH 开头的 CTE
        if not upper.startswith("WITH"):
            raise ValueError(f"只允许只读查询 (SELECT/WITH/EXPLAIN), 检测到不允许的语句: {query[:80]}")
    if _FORBIDDEN_KEYWORDS.search(query):
        # 对于 SELECT/WITH 中的子查询, 允许但需要检查外层
        pass

async def _execute_sql(query: str) -> list[dict[str, Any]]:
    _check_sql_readonly(query)
    # 用 psql 执行(也可以用 asyncpg, 但 psql 更通用无需额外包)
    dsn = DB_DSN
    cmd = ["psql", dsn, "-t", "-A", "-F", "\t", "--no-align", "--field-separator=|", "-c", query]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"SQL 执行失败: {stderr.decode()}")
    lines = stdout.decode().strip().split("\n")
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return []
    # 简化返回: 每行一条记录
    result = []
    for line in lines[:200]:
        parts = line.split("|")
        result.append({f"col{i}": p for i, p in enumerate(parts)})
    return result

# ── 日志工具 ─────────────────────────────────────────────────────────

_LOG_MAP = {
    "backend": "uvicorn.out",
    "auth": "auth.log",
    "agent": "agent.log",
    "codemap": "codemap.log",
    "knowledge": None,  # 尝试 modules/knowledge.log
    "docs-open": "docs-open.log",
    "image-gen": "image-gen.log",
    "file-transfer": "file_transfer.log",
    "gateway": "gateway.log",
    "im": "im.log",
    "command-safety": "command_safety.log",
}

def _tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return f"[文件不存在] {path}"
    # 用 subprocess tail 命令
    try:
        result = subprocess.run(
            ["tail", f"-n{lines}", str(path)],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "[错误] tail 超时"
    except Exception as e:
        return f"[错误] {e}"


def _clear_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text("", encoding="utf-8")
    tmp_path.replace(path)


def _resolve_log_paths(module: str, *, all_logs: bool = False) -> list[Path]:
    if all_logs:
        return sorted(path for path in LOG_DIR.rglob("*.log") if path.is_file())

    module_key = module.strip().lower()
    mapped = _LOG_MAP.get(module_key)
    if mapped is None:
        candidates = [
            LOG_DIR / f"modules/{module_key}.log",
            LOG_DIR / f"modules/{module_key.replace('-', '_')}.log",
            LOG_DIR / f"modules/{module_key.replace('_', '-')}.log",
        ]
        return [path for path in candidates if path.exists()]
    return [LOG_DIR / mapped]


def _clear_log(module: str = "backend", all_logs: bool = False, keep_state: bool = True) -> dict[str, Any]:
    cleared: list[str] = []
    missing: list[str] = []

    for path in _resolve_log_paths(module, all_logs=all_logs):
        if path.exists() and path.is_file():
            _clear_file(path)
            cleared.append(str(path.relative_to(REPO_ROOT)))
        else:
            missing.append(str(path.relative_to(REPO_ROOT)))

    preserved = []
    if keep_state:
        preserved = [
            str((LOG_DIR / ".backend.port").relative_to(REPO_ROOT)),
            str((LOG_DIR / ".watchdog.pid").relative_to(REPO_ROOT)),
        ]

    return {
        "success": True,
        "module": module,
        "all": all_logs,
        "keep_state": keep_state,
        "cleared": cleared,
        "missing": missing,
        "preserved": preserved,
    }

    if UPLOADS_DIR.exists():
        for path in UPLOADS_DIR.rglob("*"):
            if not path.is_file():
                continue
            if _is_knowledge_noise_name(path.name):
                try:
                    path.unlink()
                    removed_uploads.append(str(path.relative_to(REPO_ROOT)))
                except FileNotFoundError:
                    pass

    if MEMORY_DIR.exists():
        for path in MEMORY_DIR.glob("*.md"):
            if path.name.startswith("_"):
                continue
            if _is_knowledge_noise_name(path.name):
                try:
                    path.unlink()
                    removed_memory.append(str(path.relative_to(REPO_ROOT)))
                except FileNotFoundError:
                    pass

    try:
        if removed_memory:
            _update_index()
    except Exception:
        pass

    return {
        "removed_uploads": removed_uploads,
        "removed_memory": removed_memory,
        "upload_count": len(removed_uploads),
        "memory_count": len(removed_memory),
    }


def _knowledge_noise_report() -> dict[str, Any]:
    upload_counts = Counter()
    upload_samples: list[str] = []
    if UPLOADS_DIR.exists():
        # collect suspicious names from all upload files
        for path in UPLOADS_DIR.rglob("*"):
            if not path.is_file():
                continue
            if _is_knowledge_noise_name(path.name):
                upload_counts[path.suffix.lower() or "(no_ext)"] += 1
                if len(upload_samples) < 40:
                    upload_samples.append(str(path.relative_to(REPO_ROOT)))

    memory_samples: list[str] = []
    if MEMORY_DIR.exists():
        for path in MEMORY_DIR.glob("*.md"):
            if path.name.startswith("_"):
                continue
            if _is_knowledge_noise_name(path.name):
                if len(memory_samples) < 40:
                    memory_samples.append(str(path.relative_to(REPO_ROOT)))

    return {
        "upload_noise_count": sum(upload_counts.values()),
        "upload_noise_by_suffix": dict(upload_counts),
        "upload_noise_samples": upload_samples,
        "memory_noise_count": len(memory_samples),
        "memory_noise_samples": memory_samples,
        "hint": "这些名字看起来像测试/烟雾/验收产物，可用 knowledge_cleanup_noise 清理。",
    }


async def _run_psql(sql: str, timeout: int = 60) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "psql",
        DB_DSN,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return proc.returncode, stdout.decode(), stderr.decode()


async def _fetch_table_count(table: str) -> int:
    code, out, err = await _run_psql(f"SELECT count(*) FROM {table};", timeout=30)
    if code != 0:
        raise RuntimeError(err.strip() or f"count query failed for {table}")
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return 0


async def _workspace_audit() -> dict[str, Any]:
    tables = [
        "framework_file_items",
        "framework_file_folders",
        "framework_file_shares",
        "framework_desktop_states",
        "framework_file_recycle_items",
        "framework_file_json_packages",
        "framework_file_json_versions",
        "framework_file_json_patches",
        "framework_file_json_tasks",
        "kb_catalogs",
        "kb_documents",
        "kb_chunks",
        "kb_page_fusions",
        "kb_raw_data",
        "kb_entity_dictionary",
        "kb_entity_aliases",
        "kb_disambiguation",
        "kb_graph_nodes",
        "kb_graph_edges",
        "kb_chunk_entities",
        "kb_evidence",
        "kb_conclusion_evidence",
        "kb_entity_merge_log",
        "kb_governance_candidates",
        "kb_document_profiles",
        "kb_file_relations",
    ]
    rows = []
    for table in tables:
        try:
            rows.append({"table": table, "count": await _fetch_table_count(table)})
        except Exception as exc:
            rows.append({"table": table, "error": str(exc)})

    upload_count = 0
    if UPLOADS_DIR.exists():
        upload_count = sum(1 for p in UPLOADS_DIR.rglob("*") if p.is_file())

    noise_report = _knowledge_noise_report()
    return {
        "uploads_files": upload_count,
        "table_counts": rows,
        "noise_report": noise_report,
    }


async def _workspace_reset(confirm: str, scope: str = "all") -> dict[str, Any]:
    if confirm != "RESET":
        return {"error": "confirm must be RESET", "rejected": True}

    scope = scope.lower().strip()
    if scope not in {"all", "desktop", "knowledge", "files"}:
        return {"error": "scope must be one of all/desktop/knowledge/files", "rejected": True}

    deleted_files: list[str] = []
    if scope in {"all", "files", "knowledge"} and UPLOADS_DIR.exists():
        for path in UPLOADS_DIR.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                deleted_files.append(str(path.relative_to(REPO_ROOT)))
            except FileNotFoundError:
                continue

    table_groups = {
        "files": [
            "framework_file_shares",
            "framework_file_recycle_items",
            "framework_file_json_packages",
            "framework_file_json_versions",
            "framework_file_json_patches",
            "framework_file_json_tasks",
            "framework_file_items",
            "framework_file_folders",
            "framework_desktop_states",
        ],
        "knowledge": [
            "kb_conclusion_evidence",
            "kb_evidence",
            "kb_chunk_entities",
            "kb_graph_edges",
            "kb_graph_nodes",
            "kb_disambiguation",
            "kb_entity_aliases",
            "kb_entity_dictionary",
            "kb_raw_data",
            "kb_page_fusions",
            "kb_document_profiles",
            "kb_governance_candidates",
            "kb_chunks",
            "kb_documents",
            "kb_catalogs",
            "kb_entity_merge_log",
            "kb_file_relations",
        ],
    }
    tables_to_truncate: list[str] = []
    if scope == "all":
        tables_to_truncate = table_groups["knowledge"] + table_groups["files"]
    else:
        tables_to_truncate = table_groups[scope]

    if tables_to_truncate:
        sql = "TRUNCATE TABLE " + ", ".join(tables_to_truncate) + " RESTART IDENTITY CASCADE;"
        code, out, err = await _run_psql(sql, timeout=60)
        if code != 0:
            return {"error": err.strip() or out.strip() or "reset failed", "rejected": True}

    return {
        "success": True,
        "scope": scope,
        "truncated_tables": tables_to_truncate,
        "deleted_files": deleted_files[:200],
        "deleted_file_count": len(deleted_files),
    }





# ──────────────────── 工具: _restart_backend ───────────────────────


async def _restart_backend() -> dict[str, Any]:
    """重启后端服务并验证健康检查。"""
    import signal

    result = {"status": "ok", "restarted": False, "port": 0, "health": ""}

    # 1. 找 uvicorn 进程并杀掉
    killed = 0
    try:
        out = subprocess.run(
            ["pgrep", "-f", "uvicorn app.main:app"],
            capture_output=True, text=True, timeout=5,
        )
        for pid_str in out.stdout.strip().split("\n"):
            pid_str = pid_str.strip()
            if pid_str:
                try:
                    os.kill(int(pid_str), signal.SIGTERM)
                    killed += 1
                except OSError:
                    pass
    except Exception:
        pass

    result["killed"] = killed

    # 2. 等待端口释放
    for _ in range(5):
        try:
            subprocess.run(
                ["lsof", "-ti:33000"], capture_output=True, timeout=3,
            )
            await asyncio.sleep(1.0)
        except Exception:
            break

    # 3. 启动后端
    start_script = REPO_ROOT / "scripts" / "start_backend.sh"
    if not start_script.exists():
        result["error"] = f"start_backend.sh not found at {start_script}"
        return result

    proc = await asyncio.create_subprocess_exec(
        "zsh", str(start_script),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=str(REPO_ROOT),
    )
    stdout, stderr = await proc.communicate()
    output = (stdout + stderr).decode("utf-8", errors="replace")

    # 4. 等待健康检查
    port = 33000
    port_file = REPO_ROOT / "backend" / "logs" / ".backend.port"
    if port_file.exists():
        try:
            port = int(port_file.read_text().strip())
        except (ValueError, OSError):
            port = 33000

    health = "unknown"
    for _ in range(15):
        try:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5) as c:
                r = await c.get("/api/health")
                health = r.text[:300]
                if r.status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(1.0)

    result["restarted"] = True
    result["port"] = port
    result["health"] = health
    result["output"] = output[-500:]
    return result


# ──────────────────── 工具: _verify_tool_args ──────────────────────


async def _verify_tool_args() -> dict[str, Any]:
    """存入 tool_call 事件并投影, 验证 arguments 类型。"""

    result: dict[str, Any] = {"ok": False, "arguments_type": "unknown", "arguments": None}

    async def _inner():
        from app.database import AsyncSessionLocal
        from sqlalchemy import select

        from modules.agent.backend.engine.event_store import project_to_messages, record_event
        from modules.agent.backend.models import AgentConversation

        async with AsyncSessionLocal() as db:
            conv = await db.scalar(
                select(AgentConversation).order_by(AgentConversation.id.desc())
            )
            if not conv:
                result["error"] = "no conversation found"
                return
            cid = conv.id
            await record_event(db, cid, "assistant_msg", {"content": "mcp-test"}, "_mcp_verify")
            await record_event(
                db, cid, "tool_call",
                {"id": "call_mcp", "name": "skill_list", "arguments": {"category": "web-tools"}},
                "_mcp_verify",
            )
            await record_event(
                db, cid, "tool_result",
                {"tool_call_id": "call_mcp", "name": "skill_list", "result": {"ok": True}},
                "_mcp_verify",
            )
            msgs = await project_to_messages(db, cid)
            for m in msgs:
                if m.get("tool_calls"):
                    tc = m["tool_calls"][0]
                    result["arguments_type"] = type(tc["function"]["arguments"]).__name__
                    result["arguments"] = tc["function"]["arguments"]
                    result["ok"] = isinstance(tc["function"]["arguments"], str)
                    result["expected"] = "str"
                    break

    try:
        await _inner()
    except Exception as e:
        result["error"] = str(e)

    return result


# ──────────────────── 工具: _snap_diff ────────────────────────────


async def _snap_diff() -> dict[str, Any]:
    """输出未提交文件的 diff 快照。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "status", "--short",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )
        out, _ = await proc.communicate()
        files = [line.strip() for line in out.decode().split("\n") if line.strip()]
        return {"files": files, "count": len(files)}
    except Exception as e:
        return {"files": [], "count": 0, "error": str(e)}

# ──────────────────── 工具 10: code_explore ──────────────────────────

_CODEGRAPH_CLI = str(Path.home() / ".npm-global" / "bin" / "codegraph")

async def _code_explore(query: str) -> str:
    """通过 codegraph 探索代码: 查符号/调用链/影响面."""
    cmd = [_CODEGRAPH_CLI, "explore", query]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps({"error": f"codegraph explore 失败: {stderr.decode()[:500]}"}, ensure_ascii=False)
    return stdout.decode() or "(空结果)"

async def _code_node(symbol: str) -> str:
    """通过 codegraph 查符号或文件的定义."""
    cmd = [_CODEGRAPH_CLI, "node", symbol]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return json.dumps({"error": f"codegraph node 失败: {stderr.decode()[:500]}"}, ensure_ascii=False)
    return stdout.decode() or "(空结果)"

async def _code_impact(path: str) -> str:
    """通过 codegraph 查文件改动的影响面."""
    cmd = [_CODEGRAPH_CLI, "impact", path]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        # fallback: codegraph node 看调用者
        fallback = [_CODEGRAPH_CLI, "node", path]
        proc2 = await asyncio.create_subprocess_exec(
            *fallback, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout2, stderr2 = await proc2.communicate()
        if proc2.returncode != 0:
            return json.dumps({"error": f"codegraph impact 失败(无fallback): {stderr.decode()[:500]}; {stderr2.decode()[:500]}"}, ensure_ascii=False)
        return stdout2.decode() or "(空结果)"
    return stdout.decode() or "(空结果)"

# ──────────────────── 工具 11: lint ──────────────────────────────────

_RUFF_CLI = str(REPO_ROOT / "backend" / ".venv" / "bin" / "ruff")

async def _lint(path: str, diff: bool = False) -> str:
    """用 ruff 静态检查 Python 文件，可选只返回可修复 diff。"""
    try:
        abs_path = _resolve_repo_path(path)
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    if not abs_path.is_file():
        return json.dumps({"success": False, "error": f"文件不存在: {abs_path}"}, ensure_ascii=False)
    cmd = [_RUFF_CLI, "check"]
    if diff:
        cmd.extend(["--diff"])
    cmd.append(str(abs_path))
    result = await _run_command_json(cmd, cwd=REPO_ROOT, timeout=60)
    output = (result.get("stdout") or "") + (result.get("stderr") or "")
    payload = {
        "success": result.get("success", False),
        "path": _repo_relative(abs_path),
        "diff": diff,
        "command": result.get("command"),
        "cwd": result.get("cwd"),
        "duration_seconds": result.get("duration_seconds"),
        "output": output or "All checks passed!",
        "output_tail": _tail_text(output) if output else "All checks passed!",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

# ──────────────────── 工具 12: routes ────────────────────────────────

async def _routes(filter_str: str = "") -> str:
    """从 openapi.json 查准后端端点."""
    url = f"{BACKEND_BASE}/openapi.json"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return json.dumps({"error": f"openapi.json 返回 {resp.status_code}"}, ensure_ascii=False)
            spec = resp.json()
    except Exception as e:
        return json.dumps({"error": f"获取 openapi.json 失败: {e}"}, ensure_ascii=False)

    paths = spec.get("paths", {})
    results = []
    f = filter_str.lower()
    for path, methods in paths.items():
        if f and f not in path.lower():
            continue
        for method, detail in methods.items():
            params = []
            for p in (detail.get("parameters") or []):
                params.append({"name": p.get("name"), "in": p.get("in"), "required": p.get("required", False)})
            req_body = detail.get("requestBody")
            if req_body:
                content = req_body.get("content", {})
                for media_type, media_detail in content.items():
                    schema = media_detail.get("schema", {})
                    params.append({"name": "(body)", "in": "body", "schema": schema})
            results.append({
                "method": method.upper(),
                "path": path,
                "summary": detail.get("summary", ""),
                "params": params,
            })
    results.sort(key=lambda r: r["path"])
    return json.dumps(results, ensure_ascii=False, indent=2)

# ──────────────────── 工具 13: capabilities ─────────────────────────

async def _capabilities(module: str = "") -> str:
    """扫描模块 manifest.json 的 public_actions."""
    modules_dir = REPO_ROOT / "modules"
    if not modules_dir.exists():
        return json.dumps({"error": "modules 目录不存在"}, ensure_ascii=False)
    results = []
    for manifest_path in sorted(modules_dir.glob("*/manifest.json")):
        mod_key = manifest_path.parent.name
        if module and mod_key != module:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            results.append({"module": mod_key, "error": str(e)})
            continue
        public_actions = manifest.get("public_actions", {})
        if isinstance(public_actions, dict):
            for action, action_detail in public_actions.items():
                params = []
                for p in action_detail.get("parameters", []):
                    params.append({"name": p.get("name", ""), "type": p.get("type", "")})
                results.append({
                    "module": mod_key,
                    "action": action,
                    "params": params,
                    "min_role": action_detail.get("min_role", ""),
                })
        elif isinstance(public_actions, list):
            for item in public_actions:
                if isinstance(item, str):
                    results.append({"module": mod_key, "action": item, "params": [], "min_role": ""})
                elif isinstance(item, dict):
                    results.append({
                        "module": mod_key,
                        "action": item.get("action", item.get("name", "")),
                        "params": item.get("parameters", []),
                        "min_role": item.get("min_role", ""),
                    })
    return json.dumps(results, ensure_ascii=False, indent=2)

# ──────────────────── 工具 14: db_schema ────────────────────────────

async def _db_schema(table: str = "") -> str:
    """查数据库表结构."""
    if not table:
        # 列出所有表名, 按前缀分组
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        rows = await _execute_sql(query)
        tables = [list(r.values())[0] for r in rows]
        # 按前缀分组
        grouped: dict[str, list[str]] = {}
        for t in tables:
            prefix = t.split("_")[0] if "_" in t else "(other)"
            grouped.setdefault(prefix, []).append(t)
        return json.dumps(grouped, ensure_ascii=False, indent=2)
    else:
        query = f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = '{table.replace("'", "''")}'
            ORDER BY ordinal_position
        """
        rows = await _execute_sql(query)
        columns = []
        for r in rows:
            vals = list(r.values())
            columns.append({
                "column": vals[0],
                "type": vals[1],
                "nullable": vals[2],
                "default": vals[3],
            })
        return json.dumps(columns, ensure_ascii=False, indent=2)

# ──────────────────── 工具 15: run_test ──────────────────────────────

async def _run_test(target: str, timeout: int = 120) -> str:
    """Run a single pytest target and return structured JSON."""
    normalized_targets = _normalize_pytest_targets(target)
    backend_dir = REPO_ROOT / "backend"
    cmd = [str(backend_dir / ".venv" / "bin" / "pytest"), *normalized_targets]
    result = await _run_command_json(cmd, cwd=backend_dir, timeout=timeout)
    return json.dumps({
        "success": result.get("success", False),
        "target": target,
        "normalized_targets": normalized_targets,
        "command": cmd,
        "cwd": result.get("cwd"),
        "duration_seconds": result.get("duration_seconds"),
        "returncode": result.get("returncode"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "stdout_tail": result.get("stdout_tail", ""),
        "stderr_tail": result.get("stderr_tail", ""),
        "timeout": result.get("timeout", False),
        "timeout_seconds": result.get("timeout_seconds"),
    }, ensure_ascii=False, indent=2)


async def _start_frontend() -> str:
    """Start the frontend dev server from the frontend directory."""
    frontend_dir = REPO_ROOT / "frontend"
    proc = await asyncio.create_subprocess_exec(
        "npm", "run", "dev",
        cwd=str(frontend_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.sleep(1)
    stdout = ""
    stderr = ""
    if proc.stdout is not None:
        try:
            stdout = (await asyncio.wait_for(proc.stdout.read(), timeout=0.5)).decode(errors="replace")
        except Exception:
            stdout = ""
    if proc.stderr is not None:
        try:
            stderr = (await asyncio.wait_for(proc.stderr.read(), timeout=0.5)).decode(errors="replace")
        except Exception:
            stderr = ""
    return json.dumps({
        "success": proc.returncode is None,
        "pid": proc.pid,
        "command": "cd frontend && npm run dev",
        "stdout": stdout,
        "stderr": stderr,
    }, ensure_ascii=False, indent=2)

async def _sanity_check() -> str:
    """Run a focused repo sanity check for common regression signals."""
    results: list[dict[str, Any]] = []

    frontend_port = await _run_command_json(
        ["lsof", "-nP", "-iTCP:5173", "-sTCP:LISTEN"],
        cwd=REPO_ROOT,
        timeout=10,
    )
    results.append({
        "check": "frontend_port_5173",
        "success": frontend_port.get("success", False),
        "details": frontend_port.get("stdout_tail") or frontend_port.get("stderr_tail") or "not listening",
    })

    backend_health = await _probe("GET", "/api/health")
    results.append({
        "check": "backend_health",
        "success": '"status": "ok"' in backend_health,
        "details": backend_health,
    })

    backend_tail = await _tail_log("backend", 80)
    import_failures = [
        line for line in backend_tail.splitlines()
        if "Failed to load module router" in line or "MODEL_PROFILES" in line
    ]
    results.append({
        "check": "backend_module_imports",
        "success": not import_failures,
        "details": import_failures[:20],
    })

    knowledge_tail = await _tail_log("knowledge", 80)
    teardown_risks = [
        line for line in knowledge_tail.splitlines()
        if "renderer.dispose is not a function" in line or "Unhandled error during execution of unmounted hook" in line
    ]
    results.append({
        "check": "knowledge_teardown",
        "success": not teardown_risks,
        "details": teardown_risks[:20],
    })

    payload = {
        "success": all(item["success"] for item in results),
        "results": results,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

async def _finish_task(
    summary: str,
    agent: str = "",
    lint_paths: str = "",
    test_targets: str = "",
    module_key: str = "",
    verification_summary: str = "",
    risk_note: str = "",
) -> str:
    """收工检查: 汇总工作区 + 边界检查 + 可选 lint/test + 风险评估 + 留痕模板。"""
    report: dict[str, Any] = {
        "success": True,
        "summary": summary,
        "agent": agent,
        "git": await _git_status_summary(),
        "boundary_check": {},
        "lint": [],
        "tests": [],
        "verification_summary": verification_summary or "(未填写验证结果)",
        "risk_note": risk_note or "(未填写)",
        "memory_write_template": {
            "agent": agent,
            "type": "task",
            "title": summary[:80] or "task summary",
            "body": "# 改了什么\n\n# 验证了什么\n\n# 是否还有残留风险\n\n# 关联 commit",
            "tags": "",
        },
    }

    # 边界检查: 模块任务校验改动只发生在允许目录
    if module_key:
        allowed_prefix = f"modules/{module_key}/"
        diff_result = await _run_command_json(
            ["git", "diff", "--name-only"],
            cwd=REPO_ROOT, timeout=10,
        )
        changed_files = [l.strip() for l in diff_result.get("stdout", "").splitlines() if l.strip()]
        violations = [f for f in changed_files if not f.startswith(allowed_prefix)]
        report["boundary_check"] = {
            "module": module_key,
            "allowed_prefix": allowed_prefix,
            "changed_files": changed_files[:50],
            "changed_count": len(changed_files),
            "violations": violations[:20],
            "violation_count": len(violations),
            "passed": len(violations) == 0,
        }
        if violations:
            report["success"] = False
            report["risk_note"] = (report["risk_note"] + f" | [边界违规] 以下改动不在 {allowed_prefix} 内: {violations[:10]}")
    else:
        # 非模块任务: 只列出改动文件
        diff_result = await _run_command_json(
            ["git", "diff", "--name-only"],
            cwd=REPO_ROOT, timeout=10,
        )
        changed_files = [l.strip() for l in diff_result.get("stdout", "").splitlines() if l.strip()]
        report["boundary_check"] = {
            "changed_files": changed_files[:50],
            "changed_count": len(changed_files),
            "note": "非模块任务，无路径约束",
        }

    for item in [p.strip() for p in re.split(r"[,\n]", lint_paths) if p.strip()]:
        try:
            lint_result = json.loads(await _lint(item))
        except json.JSONDecodeError as exc:
            lint_result = {"success": False, "path": item, "error": str(exc)}
        report["lint"].append(lint_result)
        if not lint_result.get("success"):
            report["success"] = False
    if test_targets.strip():
        try:
            test_result = json.loads(await _run_test(test_targets))
        except json.JSONDecodeError as exc:
            test_result = {"success": False, "target": test_targets, "error": str(exc)}
        report["tests"].append(test_result)
        if not test_result.get("success"):
            report["success"] = False
    return json.dumps(report, ensure_ascii=False, indent=2)


# ──────────────────── 工作流: plan_task ──────────────────────────────


def _build_evidence_checklist(task_type: str, module_key: str) -> list[dict]:
    checklist = []
    if task_type == "code_change":
        checklist.append({"tool": "code_explore", "reason": "探索相关代码：符号/调用链/影响面", "required": True})
        checklist.append({"tool": "code_node", "reason": "读取关键符号/文件定义", "required": True})
        checklist.append({"tool": "code_impact", "reason": "查看改动影响面", "required": True})
        if module_key:
            checklist.append({"tool": "routes", "params": {"filter": module_key}, "reason": "查模块相关后端端点", "required": True})
            checklist.append({"tool": "capabilities", "params": {"module": module_key}, "reason": "查模块注册能力", "required": True})
            checklist.append({"tool": "db_schema", "reason": "查模块表结构", "required": True})
    elif task_type == "investigation":
        checklist.append({"tool": "code_explore", "reason": "探索问题相关代码", "required": True})
        checklist.append({"tool": "tail_log", "reason": "查看日志排查问题", "required": True})
        checklist.append({"tool": "probe", "reason": "接口验证", "required": False})
    elif task_type == "test":
        checklist.append({"tool": "run_test", "reason": "跑测试看结果", "required": True})
        checklist.append({"tool": "probe", "reason": "接口验证", "required": False})
    return checklist


def _build_boundary(module_key: str) -> dict:
    if not module_key:
        return {
            "type": "framework/global",
            "note": "框架级改动需慎重，影响全部模块。",
        }
    return {
        "type": "module",
        "module": module_key,
        "allowed_dirs": [f"modules/{module_key}/"],
        "forbidden": [
            "禁止直接 import 其他模块代码",
            f"禁止直接读写其他模块的表（只能读写 {module_key}_* 表）",
            "禁止修改 backend/app/、frontend/src/ 或其他模块",
        ],
        "cross_module_rule": "必须通过框架统一通路：runtime SDK 或 /api/modules/call + 能力注册表",
        "validation_guard": f"验收：git diff --name-only 确认所有改动在 modules/{module_key}/ 内",
    }


def _build_verification_plan(task_type: str, module_key: str) -> dict:
    steps = []
    if task_type == "code_change":
        steps.append({"step": "lint", "tool": "lint", "target": "改动过的 Python 文件", "reason": "ruff 静态检查"})
        if module_key:
            test_path = f"backend/tests/" if module_key == "framework" else f"modules/{module_key}/sandbox/"
            steps.append({"step": "test", "tool": "run_test", "target": test_path, "reason": "模块测试", "auto": False})
        steps.append({"step": "api_check", "tool": "probe", "target": "/api/health", "reason": "后端健康检查", "auto": True})
        steps.append({"step": "log_check", "tool": "tail_log", "target": "backend", "reason": "确认无新增错误日志", "auto": True})
    return {"steps": steps, "note": "后端改动默认跑测试和 lint；接口类问题优先 probe/call_capability；日志问题先 tail_log"}


def _build_workflow(task_type: str, module_key: str) -> list[dict]:
    steps = []
    if task_type == "code_change":
        steps = [
            {"step": 1, "phase": "全景理解", "action": "调 brief() 了解项目全貌（如未调过）"},
            {"step": 2, "phase": "证据收集", "action": "按 required_evidence checklist 逐一调工具收集证据"},
            {"step": 3, "phase": "方案制定", "action": "基于证据确定具体改哪个文件、怎么改"},
            {"step": 4, "phase": "执行修改", "action": "用 quick_fix_preview 预览 → quick_fix_patch 落盘（或 Read + Edit）"},
            {"step": 5, "phase": "边界检查", "action": f"git diff --name-only 确认改动只在 modules/{module_key}/ 内" if module_key else "git diff 确认改动范围"},
            {"step": 6, "phase": "验证", "action": "按 verification_plan 跑 lint + run_test + probe + tail_log"},
            {"step": 7, "phase": "收尾留痕", "action": "finish_task(汇总+边界检查+风险评估) → memory_write(留痕)"},
        ]
    elif task_type == "investigation":
        steps = [
            {"step": 1, "phase": "问题确认", "action": "调 brief + tail_log 确认问题现象"},
            {"step": 2, "phase": "排查", "action": "code_explore + probe + db_schema 排查根因"},
            {"step": 3, "phase": "结论记录", "action": "memory_write(type='gotcha', ...) 记录排查结论"},
        ]
    elif task_type == "test":
        steps = [
            {"step": 1, "phase": "测试执行", "action": "run_test 跑测试"},
            {"step": 2, "phase": "结果分析", "action": "分析失败原因，确认是否需改代码"},
            {"step": 3, "phase": "结论记录", "action": "memory_write 记录测试结果"},
        ]
    return steps


async def _plan_task(description: str, task_type: str = "code_change", module_key: str = "") -> str:
    """
    标准任务工作流入口.
    任务开始前调此工具，自动做三件事:
    1. 预采部分证据（模块能力 / 表结构）
    2. 生成结构化计划（证据清单 / 边界 / 验证 / 工作流）
    3. 输出分步工作流，agent 须严格按步骤执行
    """
    import time as _time
    started = _time.time()

    plan: dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "type": task_type,
            "module": module_key or "(全局/框架)",
            "duration_seconds": 0,
        },
        "problem_understanding": (
            f"任务: {description}\n"
            f"类型: {task_type}\n"
            f"模块: {module_key or '(全局/框架)'}\n"
            "---\n"
            "1. 理解问题后再改代码，禁止猜测\n"
            "2. 证据收集阶段必须调足 required_evidence 中的工具\n"
            "3. 模块改动不可越界\n"
        ),
        "pre_gathered_evidence": {},
        "required_evidence": _build_evidence_checklist(task_type, module_key),
        "modification_boundary": _build_boundary(module_key),
        "verification_plan": _build_verification_plan(task_type, module_key),
        "rollback_and_risk": {
            "rollback_method": "git diff 确认范围；git checkout 回退（如未提交）；memory_write 留痕追溯",
            "risk_level": "medium" if task_type == "code_change" else "low",
            "note": "改动前先 git status 确认工作区干净；模块任务只允许改 modules/{module_key}/ 内" if module_key else "框架级改动需慎重，确认影响全部模块",
        },
        "workflow": _build_workflow(task_type, module_key),
    }

    pre_gather: dict[str, Any] = {}
    if module_key:
        try:
            capabilities_raw, db_schema_raw = await asyncio.gather(
                _capabilities(module_key),
                _db_schema(),
            )
            pre_gather["capabilities"] = json.loads(capabilities_raw) if isinstance(capabilities_raw, str) else capabilities_raw
            pre_gather["db_schema_all"] = json.loads(db_schema_raw) if isinstance(db_schema_raw, str) else db_schema_raw
        except Exception as exc:
            pre_gather["error"] = str(exc)[:200]

        # 从预采的 db_schema 中提取本模块相关表
        if "db_schema_all" in pre_gather and isinstance(pre_gather["db_schema_all"], dict):
            schema_data = pre_gather["db_schema_all"]
            module_tables = {}
            table_prefixes = [module_key, module_key.split("_")[0]] if "_" in module_key else [module_key]
            for prefix in table_prefixes:
                if prefix in schema_data:
                    module_tables[prefix] = schema_data[prefix]
            if module_tables:
                pre_gather["db_schema_module"] = module_tables

    plan["pre_gathered_evidence"] = pre_gather
    plan["metadata"]["duration_seconds"] = round(_time.time() - started, 3)
    return json.dumps(plan, ensure_ascii=False, indent=2)


# ── MCP Server ───────────────────────────────────────────────────────

server = Server("项目工具台")

# ──────────────────── 工具 1: brief ──────────────────────────────────

async def _brief() -> str:
    """项目全景摘要, 取代手读主开发文档."""
    parts = []
    # 主开发文档
    main_doc = REPO_ROOT / "开发文档" / "主开发文档.md"
    if main_doc.exists():
        text = main_doc.read_text(encoding="utf-8")
        lines = text.strip().split("\n")
        # 取前 80 行作为摘要
        summary = "\n".join(lines[:80])
        parts.append(f"## 项目概览\n{summary}\n...")
    else:
        # 改读 README
        readme = REPO_ROOT / "开发文档" / "README.md"
        if readme.exists():
            text = readme.read_text(encoding="utf-8")
            lines = text.strip().split("\n")
            summary = "\n".join(lines[:60])
            parts.append(f"## 项目概览(README)\n{summary}\n...")

    # 变更历史最近 5 条
    changelog = REPO_ROOT / "开发文档" / "变更历史.md"
    if changelog.exists():
        text = changelog.read_text(encoding="utf-8")
        # 取日期标题 + 下面几行
        entries = re.findall(r"(## .*?\n(?:.*?\n)*?)(?=## |\Z)", text)
        recent = entries[:5]
        parts.append("## 最近变更")
        for e in recent:
            parts.append(e.strip())

    # 投递箱信件标题
    inbox_dir = REPO_ROOT.parent / "华世王镞_v2邮箱" / "投递箱"
    if inbox_dir.exists():
        letters = sorted(inbox_dir.glob("*.md"))
        titles = []
        for letter in letters[-10:]:
            first_line = letter.read_text(encoding="utf-8").strip().split("\n")[0].strip("# ").strip()
            titles.append(f"- {letter.stem}: {first_line}")
        parts.append("## 投递箱待处理\n" + "\n".join(titles) if titles else "## 投递箱待处理\n(空)")

    # Git 工作区状态：让 agent 开工就知道是否在 main / 是否 dirty
    try:
        status = await _git_status_summary()
        parts.append("## Git 工作区")
        parts.append(f"- 当前分支: {status.get('branch', '')}")
        parts.append(f"- 未提交条目: {status.get('dirty_count', 0)}")
        if status.get("is_main"):
            parts.append("- 提醒: 当前在 main/master，提交前应先切分支")
        sample = status.get("sample") or []
        if sample:
            parts.append("- 变更样本: " + "；".join(sample[:12]))
    except Exception:
        pass

    # 最近活动: git commit + 项目记忆(带 agent)
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "log", "--oneline", "-5",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        git_log = stdout.decode().strip()
        if git_log:
            parts.append("## 最近 Git 提交")
            for line in git_log.split("\n"):
                parts.append(f"- {line.strip()}")
    except Exception:
        pass

    memories = _list_memories()[:5]
    if memories:
        parts.append("## 最近项目记忆")
        for m in memories:
            agent = m.get("agent", "unknown")
            parts.append(f"- {m.get('name','')} ({m.get('type','')}) [agent:{agent}] [{', '.join(m.get('tags',[]))}]")

    noise_report = _knowledge_noise_report()
    if noise_report["upload_noise_count"] or noise_report["memory_noise_count"]:
        parts.append("## 知识库污染提示")
        parts.append(
            f"- 可疑上传文件: {noise_report['upload_noise_count']} 个"
            f" | 可疑记忆文件: {noise_report['memory_noise_count']} 个"
        )
        if noise_report["upload_noise_samples"]:
            parts.append("- 上传样本: " + "；".join(noise_report["upload_noise_samples"][:8]))
        if noise_report["memory_noise_samples"]:
            parts.append("- 记忆样本: " + "；".join(noise_report["memory_noise_samples"][:8]))

    try:
        audit = await _workspace_audit()
        table_counts = audit.get("table_counts", [])
        non_zero = [row for row in table_counts if row.get("count", 0)]
        if audit.get("uploads_files", 0) or non_zero:
            parts.append("## 工作区状态")
            parts.append(f"- uploads 文件数: {audit.get('uploads_files', 0)}")
            if non_zero:
                preview = ", ".join(f"{row['table']}={row['count']}" for row in non_zero[:10])
                parts.append("- 非零表: " + preview)
    except Exception:
        pass

    return "\n\n".join(parts)

# ──────────────────── 工具 2: probe ──────────────────────────────────

async def _probe(method: str, path: str, body: str | None = None, role: str = "admin") -> str:
    """打后端任意接口, 自动登录."""
    token = await _ensure_live_token(role)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BACKEND_BASE}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        kwargs: dict[str, Any] = {"headers": headers}
        if body:
            try:
                kwargs["json"] = json.loads(body)
            except json.JSONDecodeError:
                kwargs["data"] = body
        resp = await client.request(method, url, **kwargs)
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        result = {"status_code": resp.status_code, "data": data}
        return json.dumps(result, ensure_ascii=False, indent=2)

# ──────────────────── 工具 3: call_capability ────────────────────────

async def _call_capability(module: str, action: str, params: str = "{}", role: str = "admin") -> str:
    """调模块能力(跨模块调用入口)."""
    token = await _ensure_live_token(role)
    body = {
        "target_module": module,
        "action": action,
        "parameters": json.loads(params),
    }

    async def _post_with_token(token_value: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token_value}"}
        async with httpx.AsyncClient(base_url=BACKEND_BASE, timeout=60) as client:
            return await client.post("/api/modules/call", json=body, headers=headers)

    resp = await _post_with_token(token)
    if resp.status_code == 401:
        token = await _ensure_token(role, force_refresh=True)
        _token_cache.pop(role, None)
        resp = await _post_with_token(token)

    try:
        data = resp.json()
    except Exception:
        data = resp.text
    result = {
        "status_code": resp.status_code,
        "data": data,
        "target": {"module": module, "action": action, "role": role},
    }
    return json.dumps(result, ensure_ascii=False, indent=2)

# ──────────────────── 工具 4: tail_log ───────────────────────────────

async def _tail_log(module: str = "backend", lines: int = 50) -> str:
    """查看模块日志尾部."""
    lines = min(lines, 500)

    # 直接查模块日志目录
    module_log = LOG_DIR / f"modules/{module}.log"
    if module_log.exists():
        return _tail_file(module_log, lines)

    # 查映射表
    log_file = _LOG_MAP.get(module)
    if log_file:
        path = LOG_DIR / log_file
        return _tail_file(path, lines)

    # 检查 modules/ 子目录
    for p in LOG_DIR.rglob(f"{module}.log"):
        return _tail_file(p, lines)

    # uvicorn 主日志
    main_log = LOG_DIR / "uvicorn.out"
    if main_log.exists():
        return _tail_file(main_log, lines)

    return f"[未找到模块日志] {module}"

# ──────────────────── 工具 5: sql ────────────────────────────────────

async def _sql(query: str) -> str:
    """只读 SQL 查询."""
    try:
        rows = await _execute_sql(query)
        return json.dumps(rows, ensure_ascii=False, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e), "rejected": True}, ensure_ascii=False)

# ──────────────────── 工具 6: web_read ───────────────────────────────

async def _web_read(url: str) -> str:
    """读网页返回 markdown 正文."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ProjectToolkit/1.0)"
            })
            html = resp.text
    except Exception as e:
        return f"[请求失败] {e}"

    # 优先 trafilatura
    try:
        import trafilatura
        text = trafilatura.extract(html, output_format="markdown", include_links=True)
        if text:
            return text
    except ImportError:
        pass

    # 降级: 简单 HTML 正文提取
    text = _html_to_text(html)
    if text:
        return text[:10000]

    return "[无法提取正文]"

def _html_to_text(html: str) -> str:
    """极简 HTML→纯文本."""
    # 去掉 script/style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 换行标签变回车
    html = re.sub(r"<\s*(br|/div|/p|/tr|/li|/h[1-6]|/header|/footer|/section)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # 去掉剩余标签
    html = re.sub(r"<[^>]+>", " ", html)
    # 合并空白
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()

# ──────────────────── 工具 7: memory_search ──────────────────────────

async def _memory_search(query: str, k: int = 5) -> str:
    """语义 + 关键词搜索项目记忆."""
    memories = _list_memories()
    if not memories:
        return json.dumps([], ensure_ascii=False)

    # 尝试语义搜索
    query_emb = await _get_embedding(query)
    if query_emb:
        cache = _load_embedding_cache()
        scored = []
        for m in memories:
            slug = m["slug"]
            emb = cache.get(slug)
            if emb is None:
                # 在线算嵌入
                body_text = m.get("body", "")[:512]
                if body_text:
                    emb = await _get_embedding(body_text)
                    if emb:
                        cache[slug] = emb
            if emb:
                score = _cosine_sim(query_emb, emb)
                scored.append((score, m))
        if cache:
            _save_embedding_cache(cache)
        # 按分数排序
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        results = []
        for score, m in top:
            body_preview = m.get("body", "")[:200]
            results.append({
                "name": m.get("name", m["slug"]),
                "type": m.get("type", ""),
                "tags": m.get("tags", []),
                "slug": m["slug"],
                "body": body_preview,
                "score": round(score, 4),
            })
        return json.dumps(results, ensure_ascii=False, indent=2)

    # 降级: 关键词匹配 (中文无空格, 需二元分词, 否则整串子串匹配必败)
    q = query.lower()
    words = [w.strip() for w in re.split(r'[\s,，、。!?！？:：;；]+', q) if len(w.strip()) > 1]
    # 对含中文的词补充二元分词(字符bigram), 让中文查询能命中
    bigrams = []
    for run in re.findall(r'[一-鿿]{2,}', q):
        bigrams.extend(run[i:i+2] for i in range(len(run) - 1))
    words = list(dict.fromkeys(words + bigrams))  # 去重保序
    if not words:
        words = [q]
    results = []
    for m in memories:
        body = m.get("body", "").lower()
        name = m.get("name", "").lower()
        tag_text = " ".join(m.get("tags", [])).lower()
        # 任一关键词命中即匹配
        matched_words = [w for w in words if w in body or w in name or w in tag_text]
        if matched_words:
            # score = 命中比例
            score = len(matched_words) / len(words)
            if q in name:
                score = max(score, 0.9)
            results.append({
                "name": m.get("name", m["slug"]),
                "type": m.get("type", ""),
                "tags": m.get("tags", []),
                "slug": m["slug"],
                "body": m.get("body", "")[:200],
                "score": round(score, 4),
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:k]
    return json.dumps(results, ensure_ascii=False, indent=2)

# ──────────────────── 工具 8: memory_write ──────────────────────────

async def _memory_write(type_: str, title: str, body: str, tags: str = "", agent: str = "") -> str:
    """写入一条项目记忆."""
    valid_types = {"decision", "gotcha", "architecture", "task", "reference"}
    type_ = type_ if type_ in valid_types else "reference"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    agent_val = agent.strip() or "unknown"
    slug = _slugify(title)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = MEMORY_DIR / f"{slug}.md"

    # 检查重复
    if filepath.exists():
        return json.dumps({
            "warning": f"记忆已存在 [{slug}], 未覆盖. 如需更新请手动编辑.",
            "slug": slug,
            "path": str(filepath.relative_to(REPO_ROOT)),
        }, ensure_ascii=False, indent=2)

    content = f"""---
name: "{title}"
type: {type_}
tags: [{', '.join(f'"{t}"' for t in tag_list)}]
created: {created}
agent: {agent_val}
---

{body}
"""
    filepath.write_text(content.lstrip(), encoding="utf-8")
    _update_index()

    # 算嵌入缓存
    body_text = body[:512]
    emb = await _get_embedding(body_text)
    if emb:
        cache = _load_embedding_cache()
        cache[slug] = emb
        _save_embedding_cache(cache)

    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(filepath.relative_to(REPO_ROOT)),
    }, ensure_ascii=False, indent=2)

# ──────────────────── 工具 9: memory_recent ─────────────────────────

async def _memory_recent(n: int = 10) -> str:
    """最近 N 条记忆."""
    memories = _list_memories()[:n]
    results = []
    for m in memories:
        results.append({
            "name": m.get("name", m["slug"]),
            "type": m.get("type", ""),
            "tags": m.get("tags", []),
            "slug": m["slug"],
            "created": m.get("created", ""),
        })
    return json.dumps(results, ensure_ascii=False, indent=2)

# ── 注册工具 ─────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="brief",
            description="项目全景摘要: 主开发文档概览 + 最近变更 + 投递箱待处理 + 最近项目记忆",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="probe",
            description="自动登录后打后端任意 HTTP 接口. 返回 {status_code, data}.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET/POST/PUT/DELETE)"},
                    "path": {"type": "string", "description": "API path, 如 /api/health, /api/agent/conversations"},
                    "body": {"type": "string", "description": "JSON body string (可选)"},
                    "role": {"type": "string", "description": "角色: admin/editor/viewer", "default": "admin"},
                },
                "required": ["method", "path"],
            },
        ),
        Tool(
            name="call_capability",
            description="调模块能力(跨模块调用). 自动登录后打 /api/modules/call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "模块 key, 如 knowledge, agent"},
                    "action": {"type": "string", "description": "能力名, 如 list_templates, search"},
                    "params": {"type": "string", "description": "JSON 参数", "default": "{}"},
                    "role": {"type": "string", "description": "角色: admin/editor/viewer", "default": "admin"},
                },
                "required": ["module", "action"],
            },
        ),
        Tool(
            name="tail_log",
            description="查看模块日志尾部。",
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "模块名, 为空则 backend", "default": "backend"},
                    "lines": {"type": "number", "description": "尾部行数", "default": 50},
                },
            },
        ),
        Tool(
            name="clear_log",
            description="清空项目日志文件, 默认保留 .backend.port 和 .watchdog.pid 等状态文件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "模块名, 为空则 backend", "default": "backend"},
                    "all": {"type": "boolean", "description": "是否清空所有 .log 文件", "default": False},
                    "keep_state": {"type": "boolean", "description": "是否保留端口/守护进程状态文件", "default": True},
                },
            },
        ),
        Tool(
            name="sql",
            description="只读 SQL 查询(SELECT/WITH/EXPLAIN).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "只读 SQL"},
                },
                "required": ["query"],
            },
        ),

        Tool(
            name="web_read",
            description="读网页返回 markdown 正文. 优先 trafilatura, 降级简单 HTML 提取.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页 URL"},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="memory_search",
            description="搜索项目记忆. 优先 bge-m3 语义搜索, 降级关键词匹配.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题"},
                    "k": {"type": "number", "description": "返回条数", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory_write",
            description="写入项目记忆(决策/踩坑/架构/任务/参考). 自动生成文件 + 更新索引 + 嵌入缓存.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "类型: decision/gotcha/architecture/task/reference"},
                    "title": {"type": "string", "description": "标题"},
                    "body": {"type": "string", "description": "正文"},
                    "tags": {"type": "string", "description": "逗号分隔的标签", "default": ""},
                    "agent": {"type": "string", "description": "执行 agent 标识(如 opencode, claude)", "default": ""},
                },
                "required": ["type", "title", "body"],
            },
        ),
        Tool(
            name="memory_recent",
            description="最近 N 条项目记忆.",
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "number", "description": "返回条数", "default": 10},
                },
            },
        ),
        Tool(
            name="code_explore",
            description="通过 codegraph 探索代码: 查符号/调用链/影响面. shell: codegraph explore <query>",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "符号名/文件名/自然语言问题"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="code_node",
            description="通过 codegraph 查符号或文件的定义. shell: codegraph node <symbol>",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "符号名或文件路径"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="code_impact",
            description="通过 codegraph 查文件改动的影响面. shell: codegraph impact <path>",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="quick_fix_preview",
            description=(
                "预览精准补丁: path + old_text + new_text 精确替换, "
                "可带 start_line/end_line 和 old_text sha256 防漂移; 不写盘."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "仓库内文件路径(绝对或相对仓库根)"},
                    "old_text": {"type": "string", "description": "必须唯一命中的原文块"},
                    "new_text": {"type": "string", "description": "替换后的文本块"},
                    "start_line": {"type": "number", "description": "可选: CodeGraph 定位起始行"},
                    "end_line": {"type": "number", "description": "可选: CodeGraph 定位结束行"},
                    "expected_old_text_sha256": {
                        "type": "string",
                        "description": "可选: old_text 的 sha256, 防止调用方传错块",
                        "default": "",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        ),
        Tool(
            name="quick_fix_patch",
            description=(
                "应用精准补丁: 与 quick_fix_preview 同校验, 仅 old_text 唯一命中时原子写盘; "
                "适合 CodeGraph 定位后的快速修复."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "仓库内文件路径(绝对或相对仓库根)"},
                    "old_text": {"type": "string", "description": "必须唯一命中的原文块"},
                    "new_text": {"type": "string", "description": "替换后的文本块"},
                    "start_line": {"type": "number", "description": "可选: CodeGraph 定位起始行"},
                    "end_line": {"type": "number", "description": "可选: CodeGraph 定位结束行"},
                    "expected_old_text_sha256": {
                        "type": "string",
                        "description": "可选: old_text 的 sha256, 防止调用方传错块",
                        "default": "",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        ),
        Tool(
            name="start_frontend",
            description="启动前端开发服务器，等价 cd frontend && npm run dev。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="sanity_check",
            description="规范检查: 前端端口、后端健康、模块导入失败、知识图谱卸载风险。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="smoke_all",
            description="一键全回归: 后端集测(probe/call_capability) + 前端UI(Playwright) + 红绿矩阵.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skip_ui": {"type": "boolean", "description": "跳过前端UI测试", "default": False},
                },
            },
        ),
        Tool(
            name="lint",
            description="用 ruff 静态检查 Python 文件。支持 diff=true 只预览可修复 diff，不写盘。",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Python 文件路径(绝对或相对仓库根)"},
                    "diff": {"type": "boolean", "description": "只返回 ruff --diff 预览", "default": False},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="routes",
            description="从 openapi.json 查准后端端点, 支持按路径过滤.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "路径关键词过滤", "default": ""},
                },
            },
        ),
        Tool(
            name="capabilities",
            description="扫描模块 manifest.json 查准模块能力+参数名.",
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "模块 key, 为空则列出全部", "default": ""},
                },
            },
        ),
        Tool(
            name="db_schema",
            description="查数据库表结构: 无参数列所有表(按前缀分组), 有 table 参数返回列名+类型.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "表名, 为空则列出所有表", "default": ""},
                },
            },
        ),
        Tool(
            name="run_test",
            description="跑单个测试目标，自动兼容 backend/tests、tests、绝对路径，返回结构化结果。",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "测试目标, 如 backend/tests/test_auth.py、tests/test_auth.py 或 tests/test_auth.py::test_login"},
                    "timeout": {"type": "number", "description": "超时秒数", "default": 120},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="plan_task",
            description=(
                "【标准工作流入口】任务开始前调此工具，自动预采证据并生成结构化计划。"
                "输出含：问题理解、required_evidence 清单、modification_boundary、verification_plan、workflow 步骤。"
                "agent 须严格按 workflow 步骤执行。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "任务描述"},
                    "task_type": {
                        "type": "string",
                        "description": "任务类型: code_change(默认) / investigation / test / docs",
                        "default": "code_change",
                    },
                    "module_key": {"type": "string", "description": "模块 key（如 knowledge、agent），框架/全局任务留空", "default": ""},
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="finish_task",
            description="【收工检查】汇总 Git dirty、边界检查(模块路径越界校验)、可选 lint/test、风险评估、生成 memory_write 留痕模板；不提交、不写记忆。",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "本次任务一句话摘要"},
                    "agent": {"type": "string", "description": "执行 agent 标识", "default": ""},
                    "lint_paths": {"type": "string", "description": "逗号或换行分隔的 Python 文件路径", "default": ""},
                    "test_targets": {"type": "string", "description": "pytest 目标，支持多个空格分隔", "default": ""},
                    "module_key": {"type": "string", "description": "模块 key，用于边界校验", "default": ""},
                    "verification_summary": {"type": "string", "description": "验证结果摘要", "default": ""},
                    "risk_note": {"type": "string", "description": "残留风险评估", "default": ""},
                },
                "required": ["summary"],
            },
        ),
        Tool(
            name="knowledge_noise_report",
            description="扫描知识库相关的测试/烟雾/验收污染文件，返回可疑落盘样本与统计。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="knowledge_cleanup_noise",
            description="删除知识库相关的测试/烟雾/验收污染文件(上传目录 + 记忆目录中可疑文件)。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="workspace_audit",
            description="盘点工作区数据现状: 桌面文件/知识库表/上传文件/污染样本。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="workspace_reset",
            description="一键重置工作区数据(需 confirm=RESET, scope=all/desktop/knowledge/files)。",
            inputSchema={
                "type": "object",
                "properties": {
                    "confirm": {"type": "string", "description": "必须传 RESET"},
                    "scope": {"type": "string", "description": "all/desktop/knowledge/files", "default": "all"},
                },
                "required": ["confirm"],
            },
        ),
        Tool(
            name="_restart_backend",
            description="重启后端服务 (kill uvicorn + start_backend.sh). 返回健康检查和端口。",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="_verify_tool_args",
            description="存入一条 tool_call 事件并投影为消息, 确认 arguments 是 JSON string 而非 dict.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="_snap_diff",
            description="输出当前未提交 diff 的文件名列表，只检查不用 --name-only 脏检查，结果直接返回。",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]

# ── 工具执行 ──────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "brief":
            result = await _brief()
        elif name == "probe":
            result = await _probe(
                method=arguments["method"],
                path=arguments["path"],
                body=arguments.get("body"),
                role=arguments.get("role", "admin"),
            )
        elif name == "call_capability":
            result = await _call_capability(
                module=arguments["module"],
                action=arguments["action"],
                params=arguments.get("params", "{}"),
                role=arguments.get("role", "admin"),
            )
        elif name == "tail_log":
            result = await _tail_log(
                module=arguments.get("module", "backend"),
                lines=arguments.get("lines", 50),
            )
        elif name == "clear_log":
            result = json.dumps(
                _clear_log(
                    module=arguments.get("module", "backend"),
                    all_logs=bool(arguments.get("all", False)),
                    keep_state=bool(arguments.get("keep_state", True)),
                ),
                ensure_ascii=False,
                indent=2,
            )
        elif name == "sql":
            result = await _sql(query=arguments["query"])
        elif name == "web_read":
            result = await _web_read(url=arguments["url"])
        elif name == "memory_search":
            result = await _memory_search(
                query=arguments["query"],
                k=int(arguments.get("k", 5)),
            )
        elif name == "memory_write":
            result = await _memory_write(
                type_=arguments["type"],
                title=arguments["title"],
                body=arguments["body"],
                tags=arguments.get("tags", ""),
                agent=arguments.get("agent", ""),
            )
        elif name == "memory_recent":
            result = await _memory_recent(n=int(arguments.get("n", 10)))
        elif name == "code_explore":
            result = await _code_explore(query=arguments["query"])
        elif name == "code_node":
            result = await _code_node(symbol=arguments["symbol"])
        elif name == "code_impact":
            result = await _code_impact(path=arguments["path"])
        elif name == "quick_fix_preview":
            result = json.dumps(
                quick_fix_preview(
                    repo_root=REPO_ROOT,
                    path=arguments["path"],
                    old_text=arguments["old_text"],
                    new_text=arguments["new_text"],
                    start_line=arguments.get("start_line"),
                    end_line=arguments.get("end_line"),
                    expected_old_text_sha256=arguments.get("expected_old_text_sha256", ""),
                ),
                ensure_ascii=False,
                indent=2,
            )
        elif name == "quick_fix_patch":
            result = json.dumps(
                quick_fix_patch(
                    repo_root=REPO_ROOT,
                    path=arguments["path"],
                    old_text=arguments["old_text"],
                    new_text=arguments["new_text"],
                    start_line=arguments.get("start_line"),
                    end_line=arguments.get("end_line"),
                    expected_old_text_sha256=arguments.get("expected_old_text_sha256", ""),
                ),
                ensure_ascii=False,
                indent=2,
            )
        elif name == "start_frontend":
            result = await _start_frontend()
        elif name == "sanity_check":
            result = await _sanity_check()
        elif name == "plan_task":
            result = await _plan_task(
                description=arguments["description"],
                task_type=arguments.get("task_type", "code_change"),
                module_key=arguments.get("module_key", ""),
            )
        elif name == "finish_task":
            result = await _finish_task(
                summary=arguments["summary"],
                agent=arguments.get("agent", ""),
                lint_paths=arguments.get("lint_paths", ""),
                test_targets=arguments.get("test_targets", ""),
                module_key=arguments.get("module_key", ""),
                verification_summary=arguments.get("verification_summary", ""),
                risk_note=arguments.get("risk_note", ""),
            )
        elif name == "knowledge_noise_report":
            result = await _lint(path=arguments["path"], diff=bool(arguments.get("diff", False)))
        elif name == "routes":
            result = await _routes(filter_str=arguments.get("filter", ""))
        elif name == "capabilities":
            result = await _capabilities(module=arguments.get("module", ""))
        elif name == "db_schema":
            result = await _db_schema(table=arguments.get("table", ""))
        elif name == "run_test":
            result = await _run_test(
                target=arguments["target"],
                timeout=int(arguments.get("timeout", 120)),
            )
        elif name == "plan_task":
            result = await _plan_task(
                description=arguments["description"],
                task_type=arguments.get("task_type", "code_change"),
                module_key=arguments.get("module_key", ""),
            )
        elif name == "finish_task":
            result = await _finish_task(
                summary=arguments["summary"],
                agent=arguments.get("agent", ""),
                lint_paths=arguments.get("lint_paths", ""),
                test_targets=arguments.get("test_targets", ""),
                module_key=arguments.get("module_key", ""),
                verification_summary=arguments.get("verification_summary", ""),
                risk_note=arguments.get("risk_note", ""),
            )
        elif name == "knowledge_noise_report":
            result = json.dumps(_knowledge_noise_report(), ensure_ascii=False, indent=2)
        elif name == "knowledge_cleanup_noise":
            result = json.dumps(_cleanup_knowledge_noise(), ensure_ascii=False, indent=2)
        elif name == "workspace_audit":
            result = json.dumps(await _workspace_audit(), ensure_ascii=False, indent=2)
        elif name == "workspace_reset":
            result = json.dumps(
                await _workspace_reset(
                    confirm=arguments["confirm"],
                    scope=arguments.get("scope", "all"),
                ),
                ensure_ascii=False,
                indent=2,
            )
        elif name == "_restart_backend":
            result = json.dumps(await _restart_backend(), ensure_ascii=False, indent=2)
        elif name == "_verify_tool_args":
            result = json.dumps(await _verify_tool_args(), ensure_ascii=False, indent=2)
        elif name == "_snap_diff":
            result = json.dumps(await _snap_diff(), ensure_ascii=False, indent=2)
        else:
            result = json.dumps({"error": f"未知工具: {name}"})
        return [TextContent(type="text", text=result)]
    except QuickFixError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e), "rejected": True}, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]

# ── 入口 ─────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="项目工具台",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
