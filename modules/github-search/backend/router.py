"""FastAPI router for github-search module.

Cross-module capabilities:
  github-search:search      — Search GitHub repos with ranking
  github-search:search_code — Search code on GitHub
"""
import logging
import re as _re

from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.module_registry import register_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .services.github_client import (
    get_repo_readme,
    search_code,
    search_repositories,
)

logger = logging.getLogger("v2.github-search")

router = APIRouter(prefix="/api/github-search", tags=["github-search"])


def _extract_owner_repo(url: str) -> tuple[str, str] | None:
    m = _re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if m:
        return m.group(1), m.group(2).rstrip("/")
    parts = url.strip("/").split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None


def _format_repo_result(repo: dict) -> dict:
    owner, repo_name = _extract_owner_repo(repo.get("fullName", repo.get("url", ""))) or ("", "")
    license_info = repo.get("license")
    if isinstance(license_info, dict):
        license_str = license_info.get("spdx_id", license_info.get("key", ""))
    else:
        license_str = str(license_info or "")

    return {
        "name": repo.get("fullName", ""),
        "url": repo.get("url", f"https://github.com/{owner}/{repo_name}"),
        "description": repo.get("description", "") or "",
        "stars": repo.get("stargazersCount", 0),
        "language": repo.get("language") or "",
        "license": license_str,
        "last_updated": repo.get("pushedAt", ""),
        "open_issues": repo.get("openIssuesCount", 0),
    }


async def _cap_search(params: dict, caller: str) -> dict:
    """Search GitHub repositories with ranking."""
    query = (params.get("query") or "").strip()
    limit = int(params.get("limit", 5))
    if not query:
        return {"results": [], "error": "query is required"}

    limit = max(1, min(limit, 10))
    repos = await search_repositories(query, limit)
    if not repos:
        return {"results": [], "error": "search failed or no results"}

    results = [_format_repo_result(r) for r in repos]
    enriched = []
    for r in results:
        owner_repo = _extract_owner_repo(r["url"])
        if owner_repo:
            readme = await get_repo_readme(owner_repo[0], owner_repo[1])
            if readme:
                r["readme_preview"] = readme[:500]
        enriched.append(r)

    return {
        "results": enriched,
        "total": len(enriched),
        "query": query,
        "error": None,
    }


async def _cap_search_code(params: dict, caller: str) -> dict:
    """Search code on GitHub."""
    query = (params.get("query") or "").strip()
    language = params.get("language") or None
    limit = int(params.get("limit", 5))

    if not query:
        return {"results": [], "error": "query is required"}

    limit = max(1, min(limit, 10))
    items = await search_code(query, language, limit)
    if items is None:
        return {"results": [], "error": "search failed"}

    results = []
    for item in items:
        repo = item.get("repository", {})
        repo_name = ""
        repo_url = ""
        if isinstance(repo, dict):
            repo_name = repo.get("nameWithOwner", "")
            repo_url = repo.get("url", "")
        results.append({
            "repository": repo_name,
            "url": repo_url,
            "file_path": item.get("path", ""),
            "snippets": [
                m.get("fragment", "")
                for m in (item.get("textMatches") or [])
            ],
        })

    return {"results": results, "total": len(results), "query": query, "error": None}


# ── HTTP endpoints for direct testing ──────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class SearchCodeRequest(BaseModel):
    query: str
    language: str | None = None
    limit: int = 5


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "github-search", "status": "ok"})


@router.post("/search")
async def http_search(
    body: SearchRequest,
    user: User = Depends(require_permission("viewer")),
):
    result = await _cap_search(body.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


@router.post("/search-code")
async def http_search_code(
    body: SearchCodeRequest,
    user: User = Depends(require_permission("viewer")),
):
    result = await _cap_search_code(body.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


# ── Register capabilities with framework ──────────────────────────────

register_capability(
    "github-search", "search", _cap_search,
    description="搜索 GitHub 开源项目，按活跃度和质量排序。输入关键词即可，无需 GitHub 搜索语法知识。自动过滤归档和不活跃（2年以上未更新）项目。返回结果含仓库名称、描述、Stars、语言、许可证、最后更新时间。",
    brief="搜索 GitHub 项目",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如 'fastapi agent framework'",
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量（默认5，最大10）",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    min_role="viewer",
)

register_capability(
    "github-search", "search_code", _cap_search_code,
    description="在 GitHub 上搜索代码片段。返回包含匹配代码的文件路径、仓库信息和代码片段预览。支持按编程语言过滤。",
    brief="搜索 GitHub 代码",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "代码搜索关键词，如 'register_capability'",
            },
            "language": {
                "type": "string",
                "description": "编程语言过滤（可选），如 python、javascript、go",
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量（默认5，最大10）",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    min_role="viewer",
)

# ── Startup health check ──────────────────────────────────────────────
import asyncio


@router.on_event("startup")
async def _verify_gh_cli():
    result = await asyncio.create_subprocess_exec(
        "gh", "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await result.communicate()
    if result.returncode == 0:
        logger.info("gh CLI verified: %s", stdout.decode().strip())
    else:
        logger.warning("gh CLI not found — github-search module will be unavailable")
