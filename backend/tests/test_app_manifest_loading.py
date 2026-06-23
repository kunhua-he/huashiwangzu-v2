import json
from pathlib import Path

from app.services.app_service import (
    _module_manifest_to_app_payload,
    load_app_manifests,
)


def test_load_app_manifests_includes_platform_and_module_entries(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend" / "app" / "seed_data"
    backend_root.mkdir(parents=True)
    (backend_root / "apps.json").write_text(
        json.dumps([
            {
                "key": "core-system",
                "name": "System Core",
                "icon": "Setting",
                "component_key": "apps/core-system/index.vue",
                "route_prefix": "/api/system",
            }
        ]),
        encoding="utf-8",
    )

    modules_root = tmp_path / "modules"
    module_dir = modules_root / "demo-module"
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps({
            "key": "demo-module",
            "name": "Demo Module",
            "icon": "Collection",
            "component_key": "index.vue",
            "route_prefix": "/api/demo-module",
        }),
        encoding="utf-8",
    )

    import app.services.app_service as app_service

    original_apps_manifest = app_service.APPS_MANIFEST
    original_modules_root = app_service.MODULES_ROOT
    try:
        app_service.APPS_MANIFEST = backend_root / "apps.json"
        app_service.MODULES_ROOT = modules_root
        rows = load_app_manifests(modules_root)
    finally:
        app_service.APPS_MANIFEST = original_apps_manifest
        app_service.MODULES_ROOT = original_modules_root

    assert [row["key"] for row in rows] == ["core-system", "demo-module"]
    # New modules don't auto-create frontend files, so component_key reverts to empty
    assert rows[1]["component_key"] == ""
    assert rows[1]["route_prefix"] == "/api/demo-module"


def test_background_service_without_frontend_gets_empty_component_key(tmp_path: Path) -> None:
    """background-service modules without frontend/index.vue should get empty component_key."""
    module_dir = tmp_path / "bg-service"
    module_dir.mkdir(parents=True)
    manifest = {
        "key": "bg-service",
        "name": "Background Service",
        "window_type": "background-service",
        "component_key": "index.vue",
    }
    payload = _module_manifest_to_app_payload(module_dir, manifest)
    assert payload["component_key"] == "", (
        f"Expected empty component_key for background-service without frontend, got {payload['component_key']!r}"
    )


def test_background_service_with_frontend_gets_empty_component_key(tmp_path: Path) -> None:
    """background-service modules always get empty component_key regardless of frontend file."""
    module_dir = tmp_path / "bg-with-ui"
    module_dir.mkdir(parents=True)
    (module_dir / "frontend").mkdir()
    (module_dir / "frontend" / "index.vue").write_text("<template>UI</template>", encoding="utf-8")
    manifest = {
        "key": "bg-with-ui",
        "name": "Background Service With UI",
        "window_type": "background-service",
        "component_key": "index.vue",
    }
    payload = _module_manifest_to_app_payload(module_dir, manifest)
    assert payload["component_key"] == "", (
        f"Expected empty component_key for background-service, got {payload['component_key']!r}"
    )


def test_normal_module_frontend_not_found_gets_empty_component_key(tmp_path: Path) -> None:
    """Normal module without frontend component should get empty component_key."""
    module_dir = tmp_path / "frontendless"
    module_dir.mkdir()
    manifest = {
        "key": "frontendless",
        "name": "No Frontend",
        "component_key": "index.vue",
    }
    payload = _module_manifest_to_app_payload(module_dir, manifest)
    assert payload["component_key"] == "", (
        f"Expected empty component_key for module without frontend, got {payload['component_key']!r}"
    )


def test_normal_module_with_frontend_keeps_component_key(tmp_path: Path) -> None:
    """Normal module with frontend/index.vue should keep its component_key."""
    module_dir = tmp_path / "has-frontend"
    module_dir.mkdir(parents=True)
    (module_dir / "frontend").mkdir()
    (module_dir / "frontend" / "index.vue").write_text("<template>Hello</template>", encoding="utf-8")
    manifest = {
        "key": "has-frontend",
        "name": "Has Frontend",
        "component_key": "index.vue",
    }
    payload = _module_manifest_to_app_payload(module_dir, manifest)
    assert payload["component_key"] == "has-frontend/index.vue", (
        f"Expected component_key='has-frontend/index.vue', got {payload['component_key']!r}"
    )
