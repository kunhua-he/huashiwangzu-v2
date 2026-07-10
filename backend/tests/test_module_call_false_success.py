"""Regression tests for cross-module call response truthfulness."""

from types import SimpleNamespace

import pytest
from app.core.exceptions import PermissionDenied, ValidationError
from app.routers import modules as modules_router
from app.services.module_registry import (
    call_capability,
    call_capability_as_system,
    call_capability_for_user,
    register_capability,
    semantic_failure_reason,
    unregister_capability,
)
from app.services.semantic_failure import semantic_failure_reason as pure_semantic_failure_reason


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"success": False, "error": "tool failed"}, "tool failed"),
        ({"error": "error-only failure"}, "error-only failure"),
        ({"status": "failed", "error": "status failed"}, "status failed"),
        ({"status": "failed", "reason": "parse failed clearly"}, "parse failed clearly"),
        ({"status": "failed", "error_message": "queue failed clearly"}, "queue failed clearly"),
        ({"status": "failed", "message": "message failed clearly"}, "message failed clearly"),
        ({"status": "error"}, "result.status=error"),
        ({"code": 1, "msg": "legacy failed"}, "legacy failed"),
        ({"success": True, "data": {"success": False, "error": "inner failed"}}, "inner failed"),
        ({"success": True, "data": {"error": "inner error-only"}}, "inner error-only"),
    ],
)
def test_semantic_failure_reason_covers_false_green_shapes(payload, expected) -> None:
    assert semantic_failure_reason(payload) == expected


def test_semantic_failure_reason_allows_non_failure_status() -> None:
    assert semantic_failure_reason({"status": "skipped", "reason": "source_file_deleted"}) is None
    assert semantic_failure_reason({"status": "degraded", "reason": "partial"}) is None
    assert semantic_failure_reason is pure_semantic_failure_reason


@pytest.mark.asyncio
async def test_module_call_preserves_capability_failure_status(monkeypatch) -> None:
    async def fake_call_capability(*args, **kwargs):
        return {"success": True, "data": {"error": "inner failure"}}

    monkeypatch.setattr(modules_router, "call_capability_for_user", fake_call_capability)

    with pytest.raises(ValidationError) as exc_info:
        await modules_router.module_call(
            modules_router.ModuleCallRequest(
                target_module="demo",
                action="run",
                parameters={},
            ),
            user=SimpleNamespace(id=1, role="viewer"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.message == "inner failure"


@pytest.mark.asyncio
async def test_user_cannot_self_report_privileged_role() -> None:
    async def fake_handler(params: dict, caller: str) -> dict:
        return {"caller": caller, "params": params}

    register_capability(
        "_test_auth_contract",
        "admin_only",
        fake_handler,
        min_role="admin",
    )
    try:
        with pytest.raises(PermissionDenied, match="trusted authentication context"):
            await call_capability(
                "_test_auth_contract",
                "admin_only",
                {},
                caller="user:4",
                caller_role="admin",
            )
    finally:
        unregister_capability("_test_auth_contract", "admin_only")


@pytest.mark.asyncio
async def test_authenticated_helper_supplies_user_role() -> None:
    async def fake_handler(params: dict, caller: str) -> dict:
        return {"caller": caller, "params": params}

    register_capability(
        "_test_auth_contract",
        "admin_only",
        fake_handler,
        min_role="admin",
    )
    try:
        result = await call_capability_for_user(
            "_test_auth_contract",
            "admin_only",
            {"ok": True},
            user=SimpleNamespace(id=7, role="admin"),
        )
    finally:
        unregister_capability("_test_auth_contract", "admin_only")

    assert result == {"caller": "user:7", "params": {"ok": True}}


@pytest.mark.asyncio
async def test_unknown_system_principal_is_denied() -> None:
    async def fake_handler(params: dict, caller: str) -> dict:
        return {"caller": caller, "params": params}

    register_capability(
        "_test_auth_contract",
        "admin_only",
        fake_handler,
        min_role="admin",
    )
    try:
        with pytest.raises(PermissionDenied, match="Unknown system principal"):
            await call_capability_as_system(
                "_test_auth_contract",
                "admin_only",
                {},
                principal="system:not-registered",
                on_behalf_of_user_id=8,
            )
    finally:
        unregister_capability("_test_auth_contract", "admin_only")
