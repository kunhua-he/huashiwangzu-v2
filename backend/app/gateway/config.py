"""Gateway configuration — shared config loader for router and service.

Config loading lives here so that ``service.py`` can read model profiles and
provider config without importing private symbols from ``router.py``.

v2 model governance: provider → model_capability → variant_template → routing_policy.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("v2.gateway.config")

DEFAULT_MODEL = "deepseek-v4-flash"

_MODELS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "config" / "models.json"
)

_CONFIG: dict | None = None


@dataclass
class VariantTemplate:
    """A named model template — the unit of role routing.

    Each template references a primary profile and a fallback chain.
    Agent roles (planner/executor/reviewer/etc.) resolve their model
    selection through templates rather than direct profile keys.
    """
    name: str
    description: str = ""
    primary_profile: str = DEFAULT_MODEL
    fallback_chain: list[str] = field(default_factory=list)
    budget_ratio: float = 1.0


@dataclass
class RoutingPolicy:
    """Maps agent roles → variant templates under contextual conditions.

    ``rules``: dict of role_name → template_name (the base mapping).
    ``high_ambiguity_override``: template to use when task ambiguity is high.
    ``high_cost_override``: template to use when task cost tolerance is high.
    ``budget_tight_override``: template to use when remaining budget is low.
    """
    name: str = "default_policy"
    description: str = ""
    rules: dict[str, str] = field(default_factory=dict)
    high_ambiguity_override: str = "planner"
    high_cost_override: str = "planner"
    budget_tight_override: str = "executor"

    def resolve_template(self, role: str, high_ambiguity: bool = False,
                         high_cost: bool = False, budget_tight: bool = False) -> str:
        if budget_tight and self.budget_tight_override:
            return self.budget_tight_override
        if high_cost and self.high_cost_override:
            return self.high_cost_override
        if high_ambiguity and self.high_ambiguity_override:
            return self.high_ambiguity_override
        return self.rules.get(role, self.rules.get("default", "default"))


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

TEMPLATES: dict[str, VariantTemplate] = {}
_raw_templates = _config.get("templates", {})
for _name, _tpl in _raw_templates.items():
    TEMPLATES[_name] = VariantTemplate(
        name=_name,
        description=_tpl.get("description", ""),
        primary_profile=_tpl.get("primary_profile", DEFAULT_MODEL),
        fallback_chain=_tpl.get("fallback_chain", []),
        budget_ratio=_tpl.get("budget_ratio", 1.0),
    )

ROUTING_POLICIES: dict[str, RoutingPolicy] = {}
_raw_policies = _config.get("routing_policies", {})
for _pname, _pol in _raw_policies.items():
    ROUTING_POLICIES[_pname] = RoutingPolicy(
        name=_pname,
        description=_pol.get("description", ""),
        rules=_pol.get("rules", {}),
        high_ambiguity_override=_pol.get("high_ambiguity_override", "planner"),
        high_cost_override=_pol.get("high_cost_override", "planner"),
        budget_tight_override=_pol.get("budget_tight_override", "executor"),
    )

DEFAULT_ROUTING_POLICY = ROUTING_POLICIES.get("default_policy", RoutingPolicy())

BUDGET_RATES: dict[str, dict] = _config.get("budget_rates", {})


def resolve_api_key(provider_cfg: dict) -> str:
    env_name = provider_cfg.get("api_key_env", "")
    if not env_name:
        return ""
    from app.config import get_settings
    key = getattr(get_settings(), env_name, "")
    if not key:
        logger.warning("Provider config references %s but it is empty in settings", env_name)
    return key


def resolve_template_for_role(role: str = "default",
                               high_ambiguity: bool = False,
                               high_cost: bool = False,
                               budget_tight: bool = False,
                               policy_name: str = "default_policy") -> VariantTemplate:
    """Resolve a variant template for the given role and context."""
    policy = ROUTING_POLICIES.get(policy_name, DEFAULT_ROUTING_POLICY)
    template_name = policy.resolve_template(role, high_ambiguity, high_cost, budget_tight)
    template = TEMPLATES.get(template_name, TEMPLATES.get("default"))
    if not template:
        return VariantTemplate(name="default", primary_profile=DEFAULT_MODEL)
    return template


def list_templates() -> list[dict]:
    return [
        {"name": t.name, "description": t.description,
         "primary_profile": t.primary_profile,
         "fallback_count": len(t.fallback_chain)}
        for t in TEMPLATES.values()
    ]


def list_routing_policies() -> list[dict]:
    return [
        {"name": p.name, "description": p.description,
         "rule_count": len(p.rules)}
        for p in ROUTING_POLICIES.values()
    ]
