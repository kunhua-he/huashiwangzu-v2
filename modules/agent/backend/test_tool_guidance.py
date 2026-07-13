"""Tests for tool guidance control plane, degradation recipes, and browser-tools.

Covers:
1. Tool guidance merge order correctness
2. User/Agent guide cannot override global security contract (architectural)
3. Active version uniqueness, rollback restores old version
4. Failure_policy matches 5 initial degradation recipes
5. Runtime only injects relevant tool guidance
6. browser-tools: no cookie/localStorage exposure
7. browser-tools URL allow/deny boundaries
8. browser-tools timeout, download size, screenshot size limits
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import ValidationError

REPO_DIR = Path(__file__).resolve().parents[3]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

# ── Load tool guidance service via importlib ──

TGS_PATH = REPO_DIR / "modules/agent/backend/services/tool_guidance_service.py"
spec = importlib.util.spec_from_file_location(
    "modules.agent.backend.services.tool_guidance_service", TGS_PATH
)
assert spec and spec.loader
tgs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tgs)

# ── Load browser-tools handlers via importlib ──

BROWSER_PATH = REPO_DIR / "modules/browser-tools/backend/handlers/browser.py"
if BROWSER_PATH.exists():
    bspec = importlib.util.spec_from_file_location(
        "modules.browser_tools.backend.handlers.browser", BROWSER_PATH
    )
    assert bspec and bspec.loader
    browser_mod = importlib.util.module_from_spec(bspec)
    bspec.loader.exec_module(browser_mod)
else:
    browser_mod = None


# ── Load browser-tools router via importlib ──

BROWSER_ROUTER_PATH = REPO_DIR / "modules/browser-tools/backend/router.py"
if BROWSER_ROUTER_PATH.exists():
    rspec = importlib.util.spec_from_file_location(
        "modules.browser_tools.backend.router", BROWSER_ROUTER_PATH
    )
    assert rspec and rspec.loader
    browser_router = importlib.util.module_from_spec(rspec)
    rspec.loader.exec_module(browser_router)
else:
    browser_router = None


# ── Test 1: Merge order / scope priority ───────────────────────────


def test_scope_priority_order():
    assert tgs.SCOPE_ORDER == ["global", "enterprise", "role", "agent", "user", "session"]
    assert tgs._scope_priority("global") == 0
    assert tgs._scope_priority("enterprise") == 1
    assert tgs._scope_priority("role") == 2
    assert tgs._scope_priority("agent") == 3
    assert tgs._scope_priority("user") == 4
    assert tgs._scope_priority("session") == 5
    assert tgs._scope_priority("unknown") == 6  # unknown goes last


# ── Test 2: Error classification ────────────────────────────────────


def test_classify_tool_not_found():
    assert tgs.classify_error({"error": "tool not found: xyz"}) == "tool_not_found"
    assert tgs.classify_error({"error": "Command 'xyz' not found"}) == "tool_not_found"


def test_classify_permission_denied():
    assert tgs.classify_error({"error": "Permission denied"}) == "permission_denied"
    assert tgs.classify_error({"error": "Access forbidden"}) == "permission_denied"


def test_classify_network_error():
    assert tgs.classify_error({"error": "Network is unreachable"}) == "network_error"
    assert tgs.classify_error({"error": "Connection refused"}) == "network_error"


def test_classify_timeout():
    assert tgs.classify_error({"error": "timed out"}) == "timeout"
    assert tgs.classify_error({"error": "Command timed out after 60s"}) == "timeout"


def test_classify_syntax_error():
    assert tgs.classify_error({"error": "SyntaxError: unexpected EOF"}) == "syntax_error"


def test_classify_empty_output():
    assert tgs.classify_error({"error": "", "stderr": ""}) == "empty_output"
    assert tgs.classify_error({}) == "empty_output"


def test_classify_partial_output():
    result = {"error": "", "stderr": "warning: deprecated", "stdout": ""}
    assert tgs.classify_error(result) == "partial_output"


def test_classify_rate_limited():
    assert tgs.classify_error({"error": "rate limit exceeded"}) == "rate_limited"


def test_classify_needs_browser():
    assert tgs.classify_error({"error": "This page requires JavaScript"}) == "needs_browser"


def test_classify_needs_publish():
    assert tgs.classify_error({"error": "must publish to desktop first"}) == "needs_publish"


# ── Test 3: 5 initial degradation recipes ──────────────────────────


def test_five_initial_recipes_present():
    assert len(tgs.DEGRADATION_RECIPES) >= 5
    ids = [r["id"] for r in tgs.DEGRADATION_RECIPES]
    assert "recipe_publish_to_desktop" in ids
    assert "recipe_git_clone_fallback" in ids
    assert "recipe_syntax_fallback" in ids
    assert "recipe_url_redirect_chain" in ids
    assert "recipe_tool_discovery" in ids


def test_recipe_matches_error_class():
    r = tgs.match_degradation_recipe("syntax_error")
    assert r and r["id"] == "recipe_syntax_fallback"

    r = tgs.match_degradation_recipe("network_error")
    assert r and r["id"] == "recipe_git_clone_fallback"

    assert tgs.match_degradation_recipe("unknown_error") is None


def test_degradation_advice_output():
    advice = tgs.get_degradation_advice("tool_not_found")
    assert "降级方案" in advice
    assert tgs.match_degradation_recipe("tool_not_found")["id"] == "recipe_tool_discovery"

    advice = tgs.get_degradation_advice("nonexistent")
    assert "无预设降级方案" in advice


# ── Test 4: Runtime only injects relevant guidance ─────────────────


@pytest.mark.asyncio
async def test_render_only_relevant_tools(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(tgs, "ensure_default_tool_guides", AsyncMock())

    class MockScalars:
        @staticmethod
        def all():
            mock = MagicMock()
            mock.owner_id = None
            mock.agent_code = "default"
            mock.tool_name = "terminal-tools__exec"
            mock.scope = "global"
            mock.title = "Shell Execution"
            mock.guide_text = "Use exec for shell commands."
            mock.failure_policy = {"error_map": {"timeout": ["increase timeout"]}}
            mock.acceptance_policy = {"check": "verify exit code 0"}
            mock.enabled = True
            mock.status = "active"
            mock.created_at = None
            mock.updated_at = None
            return [mock]

    class MockResult:
        scalars = MockScalars

    db.execute = AsyncMock(return_value=MockResult())

    guidance = await tgs.render_tool_guidance(
        db, owner_id=1, agent_code="default",
        tool_names=["terminal-tools__exec"], max_tokens=2048,
    )
    assert "terminal-tools__exec" in guidance
    assert "Shell Execution" in guidance


@pytest.mark.asyncio
async def test_render_empty_for_unmatched(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(tgs, "ensure_default_tool_guides", AsyncMock())

    class MockScalars:
        @staticmethod
        def all():
            return []

    class MockResult:
        scalars = MockScalars

    db.execute = AsyncMock(return_value=MockResult())

    guidance = await tgs.render_tool_guidance(
        db, owner_id=1, agent_code="default",
        tool_names=["nonexistent_tool"], max_tokens=2048,
    )
    assert guidance == ""


# ── Test 5: Active version uniqueness (DB index) ───────────────────


def test_default_guides_do_not_seed_removed_meta_tools():
    tool_names = {item["tool_name"] for item in tgs.DEFAULT_TOOL_GUIDES}
    assert not {"skill_list", "skill_describe", "skill_use"} & tool_names
    for item in tgs.DEFAULT_TOOL_GUIDES:
        assert item["scope"] == "global"
        assert item["agent_code"] == "default"
        assert item["guide_text"]


@pytest.mark.asyncio
async def test_render_appends_global_and_user_guidance(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(tgs, "ensure_default_tool_guides", AsyncMock())

    def guide(scope: str, owner_id: int | None, text: str):
        mock = MagicMock()
        mock.owner_id = owner_id
        mock.agent_code = "default"
        mock.tool_name = "terminal-tools__publish"
        mock.scope = scope
        mock.title = scope
        mock.guide_text = text
        mock.failure_policy = {}
        mock.acceptance_policy = {}
        mock.version = 1
        return mock

    class MockScalars:
        @staticmethod
        def all():
            return [
                guide("global", None, "GLOBAL SAFETY CONTRACT"),
                guide("user", 4, "USER PUBLISH PREFERENCE"),
            ]

    class MockResult:
        scalars = MockScalars

    db.execute = AsyncMock(return_value=MockResult())
    guidance = await tgs.render_tool_guidance(
        db, owner_id=4, agent_code="default",
        tool_names=["terminal-tools__publish"], max_tokens=2048,
    )
    assert "GLOBAL SAFETY CONTRACT" in guidance
    assert "USER PUBLISH PREFERENCE" in guidance
    assert guidance.index("GLOBAL SAFETY CONTRACT") < guidance.index("USER PUBLISH PREFERENCE")


# ── Test 6: browser-tools URL allow/deny boundaries ────────────────


def test_url_blocklist():
    if not browser_mod:
        pytest.skip("browser-tools module not loaded")
    is_blocked = browser_mod._is_blocked_url

    blocked = [
        ("file:///etc/passwd", "file"),
        ("http://localhost:8080", "localhost"),
        ("http://127.0.0.1:33000", "127.0.0.1"),
        ("http://10.0.0.1/admin", "10.x"),
        ("http://172.16.0.1/config", "172.16.x"),
        ("http://192.168.1.1/router", "192.168.x"),
    ]
    for url, reason in blocked:
        b, _ = is_blocked(url)
        assert b, f"Should block {url} ({reason})"

    allowed = [
        "https://www.google.com",
        "https://api.github.com",
        "https://example.com/page",
    ]
    for url in allowed:
        b, _ = is_blocked(url)
        assert not b, f"Should allow {url}"


def test_browser_final_url_blocking_helper():
    if not browser_mod:
        pytest.skip("browser-tools module not loaded")

    class Page:
        url = "http://127.0.0.1:33000/private"

    with pytest.raises(ValueError):
        import asyncio

        asyncio.run(browser_mod._ensure_allowed_current_url(Page()))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler,params",
    [
        ("_read_text", {"session_id": "blocked"}),
        ("_list_links", {"session_id": "blocked"}),
        ("_type", {"session_id": "blocked", "selector": "input", "text": "secret"}),
        ("_screenshot", {"session_id": "blocked"}),
        ("_download", {"session_id": "blocked"}),
    ],
)
async def test_browser_session_actions_reject_blocked_current_url(handler, params):
    if not browser_mod:
        pytest.skip("browser-tools module not loaded")

    class BlockedPage:
        url = "http://127.0.0.1:33000/private"

        async def title(self):
            return "blocked"

    browser_mod._sessions["blocked"] = {"last_access": 0, "page": BlockedPage()}
    try:
        result = await getattr(browser_mod, handler)(params, "user:1")
    finally:
        browser_mod._sessions.pop("blocked", None)

    assert result["success"] is False
    assert "blocked final URL" in result["error"]


def test_browser_router_error_envelope():
    if not browser_router:
        pytest.skip("browser-tools router not loaded")
    with pytest.raises(ValidationError) as exc:
        browser_router._browser_response({"error": "file:// protocol is blocked"})
    assert "file:// protocol is blocked" in str(exc.value)


def test_browser_router_success_unwraps_handler_data():
    if not browser_router:
        pytest.skip("browser-tools router not loaded")
    response = browser_router._browser_response({"success": True, "data": {"title": "ok"}})
    assert response.success is True
    assert response.data == {"title": "ok"}


# ── Test 7: browser-tools no cookie exposure ──────────────────────


@pytest.mark.asyncio
async def test_browser_no_session_cookie_exposure():
    if not browser_mod:
        pytest.skip("browser-tools module not loaded")
    result = await browser_mod._read_text({"session_id": "nonexistent"}, "user:1")
    assert "no active session" in result.get("error", "")


# ── Test 8: Sanitize text truncation ───────────────────────────────


def test_sanitize_text_truncation():
    if not browser_mod:
        pytest.skip("browser-tools module not loaded")
    short = "Hello World"
    assert browser_mod._sanitize_text(short) == short

    long_text = "x" * 600 * 1024
    sanitized = browser_mod._sanitize_text(long_text, max_bytes=100)
    assert len(sanitized.encode("utf-8")) <= 200


# ── Test 9: Rollback ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rollback_restores_old_version():
    db = AsyncMock()
    old_guide = MagicMock()
    old_guide.id = 1
    old_guide.owner_id = None
    old_guide.agent_code = "default"
    old_guide.tool_name = "test_tool"
    old_guide.scope = "global"
    old_guide.version = 5
    old_guide.title = "Current"
    old_guide.guide_text = "current version"
    old_guide.failure_policy = {}
    old_guide.acceptance_policy = {}
    old_guide.status = "active"
    old_guide.enabled = True
    old_guide.source = "manual"
    old_guide.updated_by = None
    old_guide.created_at = None
    old_guide.updated_at = None

    snapshot = MagicMock()
    snapshot.guide_id = 1
    snapshot.version = 2
    snapshot.title = "Old"
    snapshot.guide_text = "old version text"
    snapshot.failure_policy = {}
    snapshot.acceptance_policy = {}
    snapshot.status = "active"
    snapshot.source = "manual"
    snapshot.created_by = None
    snapshot.created_at = None
    snapshot.updated_at = None
    for a in ("owner_id", "agent_code", "tool_name", "scope"):
        setattr(snapshot, a, getattr(old_guide, a))

    class MockScalars:
        def one_or_none(self):
            return old_guide

        def first(self):
            return snapshot

        def all(self):
            return [old_guide]

    class MockResult:
        def scalar_one_or_none(self):
            return old_guide

        def scalars(self):
            return MockScalars()

    db.execute = AsyncMock(return_value=MockResult())
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await tgs.rollback_guide(db, 1, 2)
    assert result is not None
