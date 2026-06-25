"""Gateway configuration — shared config loader for router and service.

Config loading lives here so that ``service.py`` can read model profiles and
provider config without importing private symbols from ``router.py``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("v2.gateway.config")

DEFAULT_MODEL = "deepseek-v4-flash"

_MODELS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "config" / "models.json"
)

_CONFIG: dict | None = None


def load_models_config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    if not _MODELS_CONFIG_PATH.exists():
        logger.warning("models.json not found at %s, gateway will use empty config", _MODELS_CONFIG_PATH)
        _CONFIG = {"providers": {}, "model_types": {"llm": {"profiles": {}}}}
        return _CONFIG
    with open(_MODELS_CONFIG_PATH) as f:
        _CONFIG = json.load(f)
    return _CONFIG


_config = load_models_config()

MODEL_PROFILES: dict[str, dict] = _config["model_types"]["llm"]["profiles"]


def resolve_api_key(provider_cfg: dict) -> str:
    env_name = provider_cfg.get("api_key_env", "")
    if not env_name:
        return ""
    from app.config import get_settings
    key = getattr(get_settings(), env_name, "")
    if not key:
        logger.warning("Provider config references %s but it is empty in settings", env_name)
    return key
