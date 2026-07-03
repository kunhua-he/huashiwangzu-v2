"""Shared diagnostics for parser-extracted embedded resources.

Parsers may still return text blocks successfully when an embedded image cannot
be extracted or persisted. This helper keeps that degraded path visible and
machine-traceable instead of silently swallowing failures.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.module_registry import call_capability

logger = logging.getLogger("v2.content").getChild("parser_resource_diagnostics")

StoreResourceCallable = Callable[[str, str, dict[str, Any], str], Awaitable[Any]]


def build_resource_diagnostic(
    *,
    stage: str,
    status: str,
    code: str,
    message: str,
    resource: dict[str, Any] | None = None,
    parser: str = "",
    error: Exception | str | None = None,
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable resource diagnostic entry with parser-local location."""
    res = resource or {}
    loc = _compact_dict({
        "resource_id": res.get("id"),
        "page": res.get("page"),
        "filename": res.get("filename"),
        "description": res.get("description") or res.get("text_desc"),
    })
    if location:
        loc.update(_compact_dict(location))

    diagnostic = _compact_dict({
        "parser": parser,
        "stage": stage,
        "status": status,
        "code": code,
        "message": message,
        "resource_ref": res.get("id"),
        "resource_type": res.get("resource_type") or res.get("type"),
        "mime_type": res.get("mime_type"),
        "location": loc,
    })
    if error is not None:
        diagnostic["error_type"] = type(error).__name__ if isinstance(error, Exception) else "Error"
        diagnostic["error_message"] = str(error)
    return diagnostic


async def store_extracted_resources_with_diagnostics(
    result: dict[str, Any],
    *,
    caller: str,
    parser: str,
    store_callable: StoreResourceCallable = call_capability,
) -> dict[str, Any]:
    """Persist parser resources and attach non-fatal diagnostics to the result.

    The parser response keeps `blocks` and `resources` usable even when resource
    storage fails. `_bytes_b64` is always removed before returning.
    """
    diagnostics = _ensure_diagnostic_list(result)
    resources = result.get("resources")
    if not isinstance(resources, list):
        result["resources"] = []
        return result

    for res in resources:
        if not isinstance(res, dict):
            diagnostics.append(build_resource_diagnostic(
                parser=parser,
                stage="store",
                status="failed",
                code="invalid_resource_entry",
                message="Parser returned a non-object resource entry.",
            ))
            continue

        already_diagnosed = bool(res.pop("_resource_diagnostic_recorded", False))
        data_b64 = str(res.pop("_bytes_b64", "") or "")
        if not data_b64:
            if not already_diagnosed:
                diagnostics.append(build_resource_diagnostic(
                    parser=parser,
                    stage="extract",
                    status="degraded",
                    code="resource_bytes_missing",
                    message="Embedded resource metadata was found, but binary bytes were unavailable.",
                    resource=res,
                ))
            continue

        try:
            stored = await store_callable(
                "content",
                "store_resource",
                {
                    "data_b64": data_b64,
                    "resource_type": res.get("resource_type") or res.get("type") or "image",
                    "mime_type": res.get("mime_type", "image/png"),
                    "filename": res.get("filename", "resource.png"),
                    "description": res.get("description") or res.get("text_desc") or "",
                },
                caller,
            )
        except Exception as exc:
            logger.warning(
                "Parser resource storage failed parser=%s resource=%s filename=%s: %s",
                parser,
                res.get("id"),
                res.get("filename"),
                exc,
            )
            diagnostics.append(build_resource_diagnostic(
                parser=parser,
                stage="store",
                status="failed",
                code="resource_store_failed",
                message="Embedded resource bytes were extracted, but resource storage failed.",
                resource=res,
                error=exc,
            ))
            continue

        if isinstance(stored, dict) and stored.get("success") is False:
            diagnostics.append(build_resource_diagnostic(
                parser=parser,
                stage="store",
                status="failed",
                code="resource_store_failed",
                message="Resource storage capability returned an explicit failure.",
                resource=res,
                error=str(stored.get("error") or "content:store_resource failed"),
            ))
            continue

        stored_payload = _unwrap_capability_payload(stored)
        stored_id = stored_payload.get("id") if isinstance(stored_payload, dict) else None
        if stored_id is None:
            diagnostics.append(build_resource_diagnostic(
                parser=parser,
                stage="store",
                status="failed",
                code="resource_store_missing_id",
                message="Resource storage completed without a traceable resource id.",
                resource=res,
            ))
            continue
        res["stored_resource_id"] = stored_id
        diagnostics.append(build_resource_diagnostic(
            parser=parser,
            stage="store",
            status="stored",
            code="resource_stored",
            message="Embedded resource was stored successfully.",
            resource=res,
            location={"stored_resource_id": stored_id},
        ))

    return result


def _ensure_diagnostic_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = result.get("resource_diagnostics")
    if isinstance(diagnostics, list):
        return diagnostics
    result["resource_diagnostics"] = []
    return result["resource_diagnostics"]


def _unwrap_capability_payload(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("data"), dict):
        return value["data"]
    return value


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v not in (None, "")}
