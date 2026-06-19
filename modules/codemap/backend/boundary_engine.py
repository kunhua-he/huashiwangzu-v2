"""Boundary rule engine for AGENTS.md rules 17-21 / C20-C21 compliance.

Checks that apply to this project:
  1. Module file MUST NOT import another module's internal files (cross-module via registry only)
  2. Module file MUST NOT import framework internals (frontend/src/*, backend/app/services/*)
  3. Module SQL MUST NOT operate on framework_* tables
  4. Module SQL MUST NOT operate on other modules' tables ({other_key}_*)
  5. Compliant cross-module: backend call_capability, frontend platform.modules.call

Each violation includes: type, rule citation, source file, target, line number.
"""

from __future__ import annotations

import logging
from typing import Any

from .graph import CodeGraph, get_graph

logger = logging.getLogger("v2.codemap.boundary")

# ── Framework-internal paths that modules must not import ────────────────────
_FRAMEWORK_INTERNAL_PREFIXES = (
    "frontend/src/",
    "backend/app/services/",
    "backend/app/models/",
    "backend/app/routers/",
    "backend/app/middleware/",
    "backend/app/schemas/",
    "backend/app/core/",
    "backend/app/gateway/",
)

# ── Framework public paths (these are OK for modules to use) ─────────────────
_FRAMEWORK_PUBLIC_PREFIXES = (
    "backend/app/database.py",
    "backend/app/config.py",
    "backend/app/core/exceptions.py",
    "backend/app/schemas/common.py",
    "backend/app/services/module_registry.py",
    "backend/app/services/task_worker.py",
    "backend/app/services/app_service.py",
    "backend/app/services/file_service.py",
    "backend/app/services/file_upload_service.py",
    "backend/app/services/file_preview_service.py",
    "backend/app/middleware/auth.py",
    "backend/app/models/app.py",
    "backend/app/models/base.py",
    "backend/app/models/file.py",
    "backend/app/models/system.py",
    "backend/app/models/user.py",
    "backend/app/gateway/router.py",
    # Frontend shared utilities are the framework's public JS surface
    "frontend/src/shared/",
)


def is_framework_internal(path: str) -> bool:
    """Check if a path points to framework internals (not public API)."""
    for public in _FRAMEWORK_PUBLIC_PREFIXES:
        if path == public or path.startswith(public) or path.endswith(public):
            return False
    for prefix in _FRAMEWORK_INTERNAL_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def is_framework_table(table_name: str) -> bool:
    """Check if a table name belongs to the framework."""
    return table_name.lower().startswith("framework_")


def get_table_module_prefix(table_name: str) -> str | None:
    """Extract module key from a table name like 'agent_conversations'.

    Returns None for unknown prefixes.
    """
    name = table_name.lower()
    if "_" not in name:
        return None
    prefix = name.split("_", 1)[0]
    # Skip common prefixes that aren't module keys
    if prefix in ("t", "v", "sys", "pg", "sql", "alembic", "test", "temp"):
        return None
    return prefix


def summarize_boundary(graph: CodeGraph | None = None) -> dict[str, Any]:
    """Return a project-wide boundary health summary."""
    g = graph or get_graph()
    modules: dict[str, dict] = {}

    for path, node in g._files.items():
        if node.layer != "module" or not node.module_key:
            continue
        mk = node.module_key
        if mk not in modules:
            modules[mk] = {"compliant": True, "violation_count": 0, "files": 0,
                           "violations": []}

        modules[mk]["files"] += 1

        for edge in g._imports.get(path, []):
            target_node = g._files.get(edge.target)
            if not target_node:
                continue

            # Check cross-module import
            if (target_node.layer == "module"
                    and target_node.module_key
                    and target_node.module_key != mk):
                modules[mk]["violations"].append({
                    "type": "cross_module_import",
                    "rule": "铁律17",
                    "source": path,
                    "target": edge.target,
                    "line": edge.line,
                })
                modules[mk]["compliant"] = False
                modules[mk]["violation_count"] += 1

            # Check framework internal import
            if is_framework_internal(edge.target):
                modules[mk]["violations"].append({
                    "type": "framework_internal_import",
                    "rule": "铁律19",
                    "source": path,
                    "target": edge.target,
                    "line": edge.line,
                })
                modules[mk]["compliant"] = False
                modules[mk]["violation_count"] += 1

        # Check DB table access
        for db_edge in g._db_tables.get(path, []):
            if is_framework_table(db_edge.table_name):
                modules[mk]["violations"].append({
                    "type": "framework_table_access",
                    "rule": "铁律17",
                    "source": path,
                    "table": db_edge.table_name,
                    "line": db_edge.line,
                })
                modules[mk]["compliant"] = False
                modules[mk]["violation_count"] += 1

            table_prefix = get_table_module_prefix(db_edge.table_name)
            if table_prefix and table_prefix != mk:
                # Check if there's a module with this key
                for other_path, other_node in g._files.items():
                    if other_node.module_key == table_prefix:
                        modules[mk]["violations"].append({
                            "type": "cross_module_table_access",
                            "rule": "铁律17",
                            "source": path,
                            "table": db_edge.table_name,
                            "owner_module": table_prefix,
                            "line": db_edge.line,
                        })
                        modules[mk]["compliant"] = False
                        modules[mk]["violation_count"] += 1
                        break

    return {
        "modules": modules,
        "total_modules": len(modules),
        "compliant_modules": sum(1 for m in modules.values() if m["compliant"]),
        "violation_modules": sum(1 for m in modules.values() if not m["compliant"]),
        "total_violations": sum(m["violation_count"] for m in modules.values()),
    }
