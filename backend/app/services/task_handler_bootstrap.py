"""Lightweight registration for durable background-task execution.

The Dispatcher needs task handlers and the capabilities invoked by those
handlers.  It does not serve HTTP, so importing every platform and module
router here would make each short-lived executor unnecessarily expensive.
"""
from __future__ import annotations

import importlib
import logging
import sys
import types

from app.routers.registry import (
    build_default_prefix_map,
    get_module_router_path,
    import_module_router,
)

logger = logging.getLogger("v2.task_handler_bootstrap")

# These modules register the durable task handlers as import side effects.
_TASK_SERVICE_MODULES = (
    ("knowledge", "services.pipeline_service"),
    ("knowledge", "services.chunk_embedding_service"),
    ("knowledge", "services.enterprise_import_service"),
)

# Parser capabilities are part of the knowledge pipeline contract.  Loading a
# parser router registers its capability but does not attach any HTTP route.
_PIPELINE_CAPABILITY_MODULES = (
    "pdf-parser",
    "docx-parser",
    "pptx-parser",
    "xlsx-parser",
    "csv-parser",
    "text-parser",
    "markdown-parser",
    "structured-parser",
    "email-parser",
    "image-vision",
)

_bootstrapped = False


def _load_module_router(module_key: str) -> None:
    router_path = get_module_router_path(module_key)
    if router_path is None:
        raise RuntimeError(f"Task bootstrap cannot find module router: {module_key}")
    import_module_router(module_key, router_path)


def _import_module_backend(module_key: str, relative_module: str) -> object:
    """Import a module implementation without executing its HTTP router."""
    router_path = get_module_router_path(module_key)
    if router_path is None:
        raise RuntimeError(f"Task bootstrap cannot find module router: {module_key}")
    if "huashiwangzu_modules" not in sys.modules:
        package = types.ModuleType("huashiwangzu_modules")
        package.__path__ = []
        sys.modules["huashiwangzu_modules"] = package
    package_name = f"huashiwangzu_modules.{module_key.replace('-', '_')}"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(router_path.parent)]
        sys.modules[package_name] = package
    return importlib.import_module(f"{package_name}.{relative_module}")


def bootstrap_task_handlers() -> None:
    """Register only the handlers and capabilities required by durable tasks.

    This runs in the long-lived Dispatcher and in each one-shot executor.  It
    intentionally never creates a FastAPI application or imports the complete
    router registry.
    """
    global _bootstrapped
    if _bootstrapped:
        return

    build_default_prefix_map()
    for module_key, relative_module in _TASK_SERVICE_MODULES:
        _import_module_backend(module_key, relative_module)

    # Agent registration is explicit by design; its HTTP router normally calls
    # this function at import time.
    agent_bootstrap = _import_module_backend("agent", "bootstrap")
    register_agent_capabilities = agent_bootstrap.register_agent_capabilities
    register_agent_tasks = agent_bootstrap.register_agent_tasks

    register_agent_tasks()
    register_agent_capabilities()

    for module_key in _PIPELINE_CAPABILITY_MODULES:
        _load_module_router(module_key)

    # These routers own both their task handlers and the capabilities called by
    # agent/scheduler tasks.  Importing them without include_router is enough.
    _load_module_router("memory")
    _load_module_router("scheduler")
    _bootstrapped = True
    logger.info("Lightweight durable task handler bootstrap completed")
