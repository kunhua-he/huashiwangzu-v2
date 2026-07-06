"""Model routing helpers for knowledge-module model stages."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.gateway.config import get_model_type_config, get_models_config, get_models_config_path

logger = logging.getLogger("v2.knowledge").getChild("model_routing")

DEFAULT_KNOWLEDGE_PROFILE = "gpt-5.5-knowledge"
DEFAULT_KNOWLEDGE_VISION_PROFILE = "gpt-5.5-vision"
KNOWLEDGE_ROUTING_KEY = "knowledge"

_STAGE_DEFAULTS: dict[str, str] = {
    "raw_ocr": DEFAULT_KNOWLEDGE_VISION_PROFILE,
    "raw_vision": DEFAULT_KNOWLEDGE_VISION_PROFILE,
    "fusion": DEFAULT_KNOWLEDGE_PROFILE,
    "profile": DEFAULT_KNOWLEDGE_PROFILE,
    "entity": DEFAULT_KNOWLEDGE_PROFILE,
    "legacy_page_fusion": DEFAULT_KNOWLEDGE_PROFILE,
}


def _knowledge_routing_config() -> dict[str, Any]:
    config = _fresh_models_config().get("module_routing", {})
    routing = config.get(KNOWLEDGE_ROUTING_KEY, {}) if isinstance(config, dict) else {}
    return routing if isinstance(routing, dict) else {}


def _fresh_models_config() -> dict[str, Any]:
    """Read models.json at stage start so runtime knobs can change between batches."""
    path = get_models_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as exc:
        logger.warning("Cannot reload models.json from %s; using cached config: %s", path, exc)
        return get_models_config()
    return config if isinstance(config, dict) else get_models_config()


def _known_llm_profiles() -> dict[str, Any]:
    profiles = get_model_type_config("llm").get("profiles", {})
    return profiles if isinstance(profiles, dict) else {}


def _known_vision_profiles() -> dict[str, Any]:
    profiles = get_model_type_config("vision").get("profiles", {})
    return profiles if isinstance(profiles, dict) else {}


def _configured_stage_profile(stage: str) -> str | None:
    routing = _knowledge_routing_config()
    stages = routing.get("stages", {}) if isinstance(routing.get("stages"), dict) else {}
    configured = stages.get(stage) or routing.get("default_profile") or _STAGE_DEFAULTS.get(stage)
    return str(configured) if configured else None


def resolve_knowledge_profile(stage: str, override: str | None = None) -> str:
    """Resolve the model profile for a knowledge LLM stage from models.json."""
    if override:
        return override

    profile = _configured_stage_profile(stage) or DEFAULT_KNOWLEDGE_PROFILE

    if profile not in _known_llm_profiles():
        logger.warning(
            "Knowledge model profile '%s' for stage=%s is not configured; using %s",
            profile,
            stage,
            DEFAULT_KNOWLEDGE_PROFILE,
        )
        return DEFAULT_KNOWLEDGE_PROFILE
    return profile


def resolve_knowledge_vision_profile(stage: str, override: str | None = None) -> str:
    """Resolve the model profile for a knowledge VLM stage from models.json."""
    if override:
        return override

    profile = _configured_stage_profile(stage) or DEFAULT_KNOWLEDGE_VISION_PROFILE

    if profile not in _known_vision_profiles():
        logger.warning(
            "Knowledge vision profile '%s' for stage=%s is not configured; using %s",
            profile,
            stage,
            DEFAULT_KNOWLEDGE_VISION_PROFILE,
        )
        return DEFAULT_KNOWLEDGE_VISION_PROFILE
    return profile


def pause_after_model_fallback() -> bool:
    """Whether a knowledge pipeline should pause after an LLM profile fallback."""
    routing = _knowledge_routing_config()
    return bool(routing.get("pause_after_fallback", True))


def should_pause_after_result(result: dict[str, Any]) -> bool:
    """Return True when a stage result should stop later deep stages."""
    if not pause_after_model_fallback():
        return False
    return bool(result.get("model_degraded"))


def resolve_knowledge_concurrency(
    stage: str,
    default: int,
    *,
    minimum: int = 1,
    maximum: int = 32,
) -> int:
    """Resolve a bounded per-stage knowledge concurrency knob from models.json."""
    routing = _knowledge_routing_config()
    raw_config = routing.get("pipeline_concurrency") or routing.get("concurrency") or {}
    config = raw_config if isinstance(raw_config, dict) else {}
    raw_value = config.get(stage)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        logger.warning("Invalid knowledge concurrency for stage=%s: %r", stage, raw_value)
        return default
    return max(minimum, min(maximum, value))
