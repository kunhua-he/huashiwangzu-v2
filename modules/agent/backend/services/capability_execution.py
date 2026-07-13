from __future__ import annotations

import logging
import re

SEP = "__"
logger = logging.getLogger("v2.agent").getChild("services.capability_execution")


def parse_capability_name(name: str) -> tuple[str, str]:
    module, separator, action = str(name or "").rpartition(SEP)
    if not separator:
        return str(name or ""), ""
    return module, action


def capability_result_succeeded(result: object) -> bool:
    if not isinstance(result, dict):
        return True
    if result.get("success") is False:
        return False
    return not bool(result.get("error"))


def capability_result_error(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("success") is False:
        return str(result.get("error") or "capability returned success=false")
    if result.get("error"):
        return str(result["error"])
    return None


def _parse_owner_id(caller: str) -> int | None:
    match = re.search(r"\buser:(\d+)\b", caller or "")
    return int(match.group(1)) if match else None


async def record_capability_invocation(
    capability_name: str,
    *,
    success: bool,
    duration_ms: float,
    caller: str,
    conversation_id: int | None = None,
    owner_id: int | None = None,
    error_detail: str | None = None,
) -> None:
    try:
        from app.database import AsyncSessionLocal

        from . import skill_governance_service as governance

        async with AsyncSessionLocal() as db:
            await governance.record_skill_usage(
                db,
                skill_name=capability_name,
                success=success,
                duration_ms=duration_ms,
                conversation_id=conversation_id,
                owner_id=owner_id if owner_id is not None else _parse_owner_id(caller),
                error_detail=error_detail,
            )
    except Exception as exc:
        logger.warning("record_capability_invocation failed (non-fatal): %s", exc)
