"""Module-specific logging (独立日志文件 + 请求 ID 贯穿).

Provides:
  - get_module_logger(module_key) → auto-configured logger writing to logs/modules/{key}.log
  - setup_module_logging() → initialize module log directory + root module log handler

Usage in module code:
    from app.services.module_logger import get_module_logger
    logger = get_module_logger("excel-engine")
    logger.info("cell updated")  # writes to logs/modules/excel-engine.log + also main log
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "modules"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 3

_initialized = False
_loggers: dict[str, logging.Logger] = {}
_LOGGER_NAME_RE = re.compile(r"^v2\.([a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*)$")


class _SafeModuleFormatter(logging.Formatter):
    """Formatter that defaults request_id to '-' when not present (e.g. background threads)."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


_SAFE_FORMAT = _SafeModuleFormatter(
    "%(asctime)s [%(name)s] %(levelname)s [%(request_id)s] %(message)s",
    datefmt="%H:%M:%S",
)


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_module_logger(module_key: str) -> logging.Logger:
    """Return a logger for *module_key* that writes to a dedicated file.

    The logger also forwards to the root handler (main backend.log).
    Safe to call multiple times — returns the same logger instance on re-import.
    """
    global _initialized
    if module_key in _loggers:
        return _loggers[module_key]

    if not _initialized:
        setup_module_logging()

    logger = logging.getLogger(f"v2.{module_key}")
    logger.setLevel(logging.INFO)

    # Check if already has a file handler for this module
    for h in logger.handlers:
        if isinstance(h, logging.Handler) and getattr(h, "baseFilename", "").endswith(f"/{module_key}.log"):
            _loggers[module_key] = logger
            return logger

    # Add rotating file handler
    _ensure_log_dir()
    log_file = LOG_DIR / f"{module_key}.log"
    handler = RotatingFileHandler(
        str(log_file),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_SAFE_FORMAT)
    logger.addHandler(handler)

    _loggers[module_key] = logger
    return logger


def setup_module_logging() -> None:
    """Initialize the module log directory and set up per-module file handlers.

    Called once at application startup from main.py.
    Scans existing v2.* loggers (from module imports during startup) and adds
    file handlers for each.
    """
    global _initialized
    if _initialized:
        return
    _ensure_log_dir()

    # Also configure the root module logger so logs from services/module_registry
    # go to the root modules.log for overview
    root_module_log = LOG_DIR.parent / "modules.log"
    root_handler = RotatingFileHandler(
        str(root_module_log),
        maxBytes=MAX_BYTES * 10,  # 100 MB for combined
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    root_handler.setFormatter(_SAFE_FORMAT)
    # Add to root logger
    logging.getLogger().addHandler(root_handler)

    _initialized = True
    logging.getLogger("v2.module_logger").info("Module logging initialised: %s", LOG_DIR)


def setup_v2_loggers_for_modules() -> None:
    """Scan existing v2.* loggers and add per-module file handlers.

    Called after module registration in the startup lifecycle.
    This catches modules that registered their loggers during import.
    """
    root_logger = logging.getLogger()
    for name in list(logging.Logger.manager.loggerDict.keys()):
        match = _LOGGER_NAME_RE.match(name)
        if match:
            module_key = name.split(".")[1]
            get_module_logger(module_key)
