"""GitHub CLI wrapper for searching repositories and code.

Uses `gh` CLI (must be installed and authenticated).
Results are structured for consumption by AI agents.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("v2.github-search").getChild("client")

_GH_TIMEOUT = 15
_MAX_SEARCH_RESULTS = 10
_CACHE_TTL = timedelta(minutes=10)

_REPO_FIELDS = [
    "fullName", "description", "stargazersCount", "forksCount",
    "pushedAt", "url", "isArchived", "isFork", "isDisabled",
    "language", "license", "openIssuesCount", "createdAt",
]

_cache: dict[str, tuple[datetime, list[dict]]] = {}


def _gh_path() -> str:
    """Return gh binary path. Prefer locally installed, fallback to PATH."""
    return os.environ.get("GH_PATH") or "gh"


async def _run_gh(args: list[str]) -> str | None:
    """Run gh CLI with timeout. Returns stdout on success, None on error."""
    cmd = [_gh_path()] + args
    logger.debug("Running: %s", " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            cmd[0], *cmd[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_GH_TIMEOUT)
        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.warning("gh CLI error (code=%d): %s", proc.returncode, err)
            return None
        return stdout.decode()
    except asyncio.TimeoutError:
        logger.warning("gh CLI timed out (%ds): %s", _GH_TIMEOUT, " ".join(args))
        return None
    except FileNotFoundError:
        logger.error("gh CLI not found. Install GitHub CLI: https://cli.github.com")
        return None
    except Exception as exc:
        logger.error("gh CLI error: %s", exc)
        return None


def _is_active(repo: dict) -> bool:
    """Filter out archived, disabled, and long-dormant repos."""
    if repo.get("isArchived") or repo.get("isDisabled"):
        return False
    pushed = repo.get("pushedAt")
    if not pushed:
        return False
    try:
        pushed_dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True
    age = datetime.now(timezone.utc) - pushed_dt
    if age > timedelta(days=365 * 2):
        return False
    return True


async def search_repositories(query: str, limit: int = 5) -> list[dict]:
    """Search GitHub repositories by keyword. Returns ranked, filtered results."""
    cache_key = f"repos:{query}:{limit}"
    cached = _cache.get(cache_key)
    if cached and (datetime.now(timezone.utc) - cached[0]) < _CACHE_TTL:
        logger.debug("Cache hit: %s", cache_key)
        return cached[1]

    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))
    fields = ",".join(_REPO_FIELDS)
    raw = await _run_gh([
        "search", "repos", query,
        "--sort", "stars",
        "--order", "desc",
        "--limit", str(limit * 2),
        "--json", fields,
    ])
    if raw is None:
        return []

    try:
        repos: list[dict] = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s", exc)
        return []

    repos = [r for r in repos if _is_active(r)]
    repos = repos[:limit]
    _cache[cache_key] = (datetime.now(timezone.utc), repos)
    return repos


async def search_code(query: str, language: str | None = None, limit: int = 5) -> list[dict]:
    """Search code on GitHub."""
    cache_key = f"code:{query}:{language}:{limit}"
    cached = _cache.get(cache_key)
    if cached and (datetime.now(timezone.utc) - cached[0]) < _CACHE_TTL:
        return cached[1]

    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))
    args = ["search", "code", query, "--limit", str(limit), "--json", "repository,path,textMatches,url"]
    if language:
        args += ["--language", language]

    raw = await _run_gh(args)
    if raw is None:
        return []

    try:
        results: list[dict] = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s", exc)
        return []

    _cache[cache_key] = (datetime.now(timezone.utc), results)
    return results


async def get_repo_readme(owner: str, repo: str) -> str | None:
    """Fetch README of a repository (text output, first 2000 chars)."""
    cache_key = f"readme:{owner}/{repo}"
    cached = _cache.get(cache_key)
    if cached and (datetime.now(timezone.utc) - cached[0]) < _CACHE_TTL:
        return cached[1][0] if cached[1] else None

    raw = await _run_gh([
        "repo", "view", f"{owner}/{repo}",
    ])
    if raw is None:
        return None

    try:
        lines = raw.split("\n", 1)
        if len(lines) > 1:
            readme = lines[1].strip()
        else:
            readme = lines[0].strip()
        _cache[cache_key] = (datetime.now(timezone.utc), [readme[:2000]])
        return readme[:2000]
    except Exception as exc:
        logger.warning("Failed to parse repo view for %s/%s: %s", owner, repo, exc)
        return None


def clear_cache() -> None:
    _cache.clear()
    logger.info("Cache cleared")
