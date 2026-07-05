import json
import logging
import os
from pathlib import Path

from .base import ImageProvider
from .gptstore import GPTStoreProvider
from .liblib import LiblibProvider
from .placeholder import PlaceholderProvider

logger = logging.getLogger("v2.image-gen").getChild("providers")

_PROVIDERS: dict[str, type[ImageProvider]] = {
    "liblib": LiblibProvider,
    "gptstore": GPTStoreProvider,
    "placeholder": PlaceholderProvider,
}

_TEMPLATES: dict = {}
_DEFAULT_TEMPLATE: str = ""

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "image_templates.json"


def _load_templates():
    global _TEMPLATES, _DEFAULT_TEMPLATE
    if not _TEMPLATES_PATH.exists():
        logger.warning("image_templates.json not found at %s", _TEMPLATES_PATH)
        _TEMPLATES = {}
        _DEFAULT_TEMPLATE = ""
        return
    with open(_TEMPLATES_PATH, "r") as f:
        cfg = json.load(f)
    _TEMPLATES = cfg.get("templates", {})
    _DEFAULT_TEMPLATE = cfg.get("default_template", "")


def get_template_config(template_key: str) -> dict | None:
    if not _TEMPLATES:
        _load_templates()
    return _TEMPLATES.get(template_key)


def get_default_template() -> str:
    if not _TEMPLATES:
        _load_templates()
    return _DEFAULT_TEMPLATE


def list_templates() -> list[dict]:
    if not _TEMPLATES:
        _load_templates()
    result = []
    for key, tpl in _TEMPLATES.items():
        provider_type = tpl.get("provider", "")
        provider_cls = _PROVIDERS.get(provider_type)
        configured = False
        if provider_cls is not None:
            configured = _check_provider_credentials(tpl)
        fallback = None
        if provider_type != "placeholder" and not configured:
            fallback = "placeholder"
        result.append({
            "key": key,
            "label": tpl.get("label", key),
            "provider": provider_type,
            "configured": configured,
            "available": configured,
            "can_generate": configured or fallback == "placeholder",
            "fallback": fallback,
            "prompt_language": tpl.get("prompt_language", "any"),
            "cost_tracking": provider_type in {"liblib", "gptstore"},
        })
    return result


def _resolve_env(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    try:
        from app.config import get_settings
        cfg = get_settings()
        return str(getattr(cfg, key, ""))
    except Exception:
        return ""


def _check_provider_credentials(template_cfg: dict) -> bool:
    provider_type = template_cfg.get("provider", "")
    if provider_type == "placeholder":
        return True
    if provider_type == "liblib":
        ak = _resolve_env(template_cfg.get("access_key_env", ""))
        sk = _resolve_env(template_cfg.get("secret_key_env", ""))
        return bool(ak and sk)
    if provider_type == "gptstore":
        from app.config import get_settings
        try:
            cfg = get_settings()
            return bool(cfg.GPTSTORE_API_KEY)
        except Exception:
            return False
    return True


def get_provider(provider_type: str) -> ImageProvider:
    cls = _PROVIDERS.get(provider_type)
    if cls is None:
        raise ValueError(f"Unknown provider type: {provider_type}")
    return cls()


def resolve_provider(template_key: str) -> tuple[ImageProvider, dict, bool]:
    cfg = get_template_config(template_key)
    if cfg is None:
        raise ValueError(f"Unknown template: {template_key}")

    provider_type = cfg.get("provider", "")
    available = _check_provider_credentials(cfg)

    if not available:
        logger.info("Template %s credentials not available, falling back to placeholder", template_key)
        placeholder_cls = _PROVIDERS.get("placeholder")
        if placeholder_cls is None:
            raise RuntimeError("Placeholder provider not registered")
        return placeholder_cls(), cfg, True

    return get_provider(provider_type), cfg, False
