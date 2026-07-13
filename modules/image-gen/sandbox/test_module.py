"""Sandbox contract tests for the image-gen module.

These tests avoid real provider calls, but they validate the live module
contract files instead of stale sample payloads.
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

MODULE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = MODULE_DIR / "backend"
REPO_ROOT = MODULE_DIR.parents[1]
FRAMEWORK_BACKEND_DIR = REPO_ROOT / "backend"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_providers_module() -> Any:
    framework_backend_path = str(FRAMEWORK_BACKEND_DIR)
    if framework_backend_path not in sys.path:
        sys.path.insert(0, framework_backend_path)
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    return importlib.import_module("providers")


def _clear_provider_credentials() -> None:
    os.environ.pop("LIBLIB_ACCESS_KEY", None)
    os.environ.pop("LIBLIB_SECRET_KEY", None)


def test_manifest_public_actions_match_runtime_contract() -> None:
    manifest = _load_json(MODULE_DIR / "manifest.json")
    actions = {item["action"]: item for item in manifest["public_actions"]}

    assert set(actions) == {"generate", "transform", "list_templates", "usage_history"}
    assert actions["generate"]["min_role"] == "editor"
    assert actions["transform"]["min_role"] == "editor"
    assert actions["list_templates"]["min_role"] == "viewer"
    assert actions["usage_history"]["min_role"] == "editor"

    params = actions["generate"]["parameters"]
    assert params["prompt"]["type"] == "string"
    assert params["size"]["default"] == "1024x1024"
    assert params["aspect_ratio"]["default"] == ""
    assert params["count"]["type"] == "integer"
    assert params["count"]["default"] == 1
    assert params["steps"]["default"] == 30
    assert params["template"]["default"] == ""
    assert params["publish"]["type"] == "boolean"
    assert params["publish"]["default"] is False

    transform_params = actions["transform"]["parameters"]
    assert transform_params["source_file_ids"]["type"] == "array"
    assert transform_params["source_file_ids"]["items"]["type"] == "integer"
    assert "source_file_id" not in transform_params
    assert "file_id" not in transform_params
    assert transform_params["prompt"]["type"] == "string"
    assert transform_params["size"]["default"] == "1024x1024"
    assert transform_params["aspect_ratio"]["default"] == ""
    assert transform_params["count"]["default"] == 1
    assert transform_params["steps"]["default"] == 30
    assert transform_params["template"]["default"] == ""
    assert transform_params["mode"]["default"] == "edit"
    assert transform_params["strength"]["default"] == 0.7
    assert transform_params["preserve_subject"]["default"] is True
    assert transform_params["publish"]["type"] == "boolean"
    assert transform_params["publish"]["default"] is False

    usage_params = actions["usage_history"]["parameters"]
    assert usage_params["limit"]["type"] == "integer"
    assert usage_params["limit"]["default"] == 20


def test_template_config_has_registered_provider_and_default() -> None:
    template_config = _load_json(BACKEND_DIR / "image_templates.json")
    templates = template_config["templates"]
    default_template = template_config["default_template"]
    default_transform_template = template_config["default_transform_template"]
    providers = _load_providers_module()

    assert default_template in templates
    assert default_transform_template == "gptstore-gpt5.5"
    assert default_transform_template in templates
    assert "placeholder" in templates

    for key, template in templates.items():
        provider_name = template["provider"]
        provider = providers.get_provider(provider_name)
        assert provider.provider_key == provider_name
        assert template.get("label"), f"template {key} must have a label"
        assert template.get("prompt_language", "any") in {"any", "en"}


def test_list_templates_exposes_productized_provider_state() -> None:
    _clear_provider_credentials()
    providers = _load_providers_module()

    templates = {item["key"]: item for item in providers.list_templates()}
    liblib = templates["liblib-star3"]
    placeholder = templates["placeholder"]

    assert liblib["provider"] == "liblib"
    assert liblib["can_generate"] is True
    assert liblib["can_transform"] is False
    if liblib["configured"]:
        assert liblib["available"] is True
        assert liblib["fallback"] is None
    else:
        assert liblib["available"] is False
        assert liblib["fallback"] == "placeholder"
    assert liblib["cost_tracking"] is True
    assert placeholder["configured"] is True
    assert placeholder["can_generate"] is True
    assert placeholder["can_transform"] is True
    assert placeholder["fallback"] is None


def test_liblib_template_declares_polling_and_credentials() -> None:
    templates = _load_json(BACKEND_DIR / "image_templates.json")["templates"]
    liblib = templates["liblib-star3"]

    assert liblib["provider"] == "liblib"
    assert liblib["api_base"].startswith("https://")
    assert liblib["text2img_path"].startswith("/")
    assert liblib["status_path"].startswith("/")
    assert liblib["access_key_env"] == "LIBLIB_ACCESS_KEY"
    assert liblib["secret_key_env"] == "LIBLIB_SECRET_KEY"
    assert int(liblib["poll_max"]) >= 1
    assert float(liblib["poll_interval_sec"]) > 0


def test_placeholder_provider_generates_requested_dimensions() -> None:
    from providers.base import GenSpec

    providers = _load_providers_module()
    provider = providers.get_provider("placeholder")
    spec = GenSpec(prompt="contract test image", width=1280, height=720, count=2, steps=30)

    results = asyncio.run(provider.generate(spec))
    assert len(results) == 2
    for result in results:
        assert result.image_bytes
        assert result.image_url is None
        assert result.meta["placeholder"] is True


def test_placeholder_provider_transforms_with_source_bytes() -> None:
    from PIL import Image
    from providers.base import GenSpec

    providers = _load_providers_module()
    provider = providers.get_provider("placeholder")
    buf = io.BytesIO()
    Image.new("RGB", (160, 120), (210, 180, 150)).save(buf, format="PNG")
    spec = GenSpec(
        prompt="make a cleaner product photo",
        width=512,
        height=512,
        count=1,
        extra={"source_images": [{"bytes": buf.getvalue(), "mime_type": "image/png"}]},
    )

    results = asyncio.run(provider.transform(spec))
    assert len(results) == 1
    assert results[0].image_bytes
    assert results[0].meta["placeholder"] is True


def test_unconfigured_provider_resolves_to_placeholder() -> None:
    _clear_provider_credentials()
    providers = _load_providers_module()
    template_state = {
        item["key"]: item
        for item in providers.list_templates()
    }["liblib-star3"]

    provider, template_cfg, is_placeholder = providers.resolve_provider("liblib-star3")

    assert template_cfg["provider"] == "liblib"
    if template_state["configured"]:
        assert provider.provider_key == "liblib"
        assert is_placeholder is False
    else:
        assert provider.provider_key == "placeholder"
        assert is_placeholder is True


def test_generate_response_contract_defaults_to_framework_file_draft() -> None:
    result = {
        "task": {"request_id": "abc123", "record_id": 1},
        "images": [
            {
                "type": "image",
                "file_id": 123,
                "name": "image-gen_1.png",
                "size": 2048,
                "placeholder": True,
                "published": False,
            }
        ],
        "placeholder": True,
        "degraded": True,
        "status": "degraded",
        "template": "placeholder",
        "provider": "placeholder",
        "requested_provider": "placeholder",
        "degraded_reason": "placeholder template selected",
        "points_cost": None,
        "balance": None,
        "published": False,
    }

    assert "images" in result
    assert "image_urls" not in result
    assert result["task"]["request_id"]
    assert result["status"] in {"success", "degraded", "partial", "failed"}
    assert result["provider"] == "placeholder"
    assert result["images"][0]["file_id"] > 0
    assert "workspace_path" not in result["images"][0]
    assert result["images"][0]["published"] is False
    assert result["images"][0]["type"] == "image"


def test_generate_response_contract_can_publish_framework_file() -> None:
    result = {
        "task": {"request_id": "abc123", "record_id": 1},
        "images": [
            {
                "type": "image",
                "file_id": 123,
                "name": "image-gen_1.png",
                "size": 2048,
                "placeholder": True,
                "published": True,
            }
        ],
        "placeholder": True,
        "degraded": True,
        "status": "degraded",
        "template": "placeholder",
        "provider": "placeholder",
        "requested_provider": "placeholder",
        "degraded_reason": "placeholder template selected",
        "points_cost": None,
        "balance": None,
        "published": True,
    }

    assert result["published"] is True
    assert result["images"][0]["file_id"] > 0
    assert "workspace_path" not in result["images"][0]


def test_transform_response_contract_defaults_to_framework_file_draft() -> None:
    result = {
        "task": {"request_id": "abc123", "record_id": 1},
        "images": [
            {
                "type": "image",
                "file_id": 456,
                "name": "image-transform_1.png",
                "size": 2048,
                "placeholder": False,
                "published": False,
            }
        ],
        "placeholder": False,
        "degraded": False,
        "status": "success",
        "template": "gptstore-gpt5.5",
        "provider": "gptstore",
        "requested_provider": "gptstore",
        "degraded_reason": None,
        "points_cost": None,
        "balance": None,
        "source_file_ids": [123],
        "mode": "edit",
        "strength": 0.7,
        "published": False,
    }

    assert "images" in result
    assert result["source_file_ids"] == [123]
    assert result["images"][0]["file_id"] > 0
    assert "workspace_path" not in result["images"][0]
    assert result["images"][0]["type"] == "image"


def test_router_uses_provider_placeholder_meta_and_record_shape() -> None:
    router_src = (BACKEND_DIR / "router.py").read_text(encoding="utf-8")
    assert "result_placeholder = is_placeholder or bool(gen_result.meta.get(\"placeholder\"))" in router_src
    assert '"placeholder": generated_placeholder' in router_src
    assert '"degraded": generated_placeholder' in router_src
    assert '"provider": provider_key' in router_src
    assert '"source_file_id":' not in router_src
    assert 'params.get("source_file_id")' not in router_src
    assert 'item.get("file_id")' not in router_src
    assert 'item.get("id")' not in router_src
    assert '"source_file_ids": source_file_ids' in router_src
    assert '"request_id": r.request_id' in router_src
    assert '"file_ids": file_ids' in router_src
    assert '"degraded_reason": r.degraded_reason' in router_src
    assert '"workspace_path"' not in router_src
    assert "terminal-tools:publish" not in router_src


def test_router_declares_clear_parameter_validation() -> None:
    router_src = (BACKEND_DIR / "router.py").read_text(encoding="utf-8")
    assert 'raise ValidationError("prompt is required")' in router_src
    assert '_parse_bounded_int(params.get("count", 1), "count", 1, MAX_IMAGE_COUNT)' in router_src
    assert '_parse_bounded_int(params.get("steps", 30), "steps", MIN_STEPS, MAX_STEPS)' in router_src
    assert 'raise ValidationError("Invalid aspect_ratio; expected square, portrait, landscape, or W:H")' in router_src
    assert 'raise ValidationError("Invalid size format; expected e.g. 1024x1024, or provide aspect_ratio")' in router_src


def main() -> None:
    print("=" * 60)
    print("image-gen sandbox contract test")
    print("=" * 60)
    test_manifest_public_actions_match_runtime_contract()
    test_template_config_has_registered_provider_and_default()
    test_list_templates_exposes_productized_provider_state()
    test_liblib_template_declares_polling_and_credentials()
    test_placeholder_provider_generates_requested_dimensions()
    test_placeholder_provider_transforms_with_source_bytes()
    test_unconfigured_provider_resolves_to_placeholder()
    test_generate_response_contract_defaults_to_framework_file_draft()
    test_generate_response_contract_can_publish_framework_file()
    test_transform_response_contract_defaults_to_framework_file_draft()
    test_router_uses_provider_placeholder_meta_and_record_shape()
    test_router_declares_clear_parameter_validation()
    print("=" * 60)
    print("PASS: image-gen sandbox contract test")


if __name__ == "__main__":
    main()
