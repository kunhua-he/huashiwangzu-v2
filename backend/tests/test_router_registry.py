import json
from pathlib import Path

from fastapi import FastAPI

from app.routers.registry import iter_module_router_files, register_routers


def test_module_router_files_are_loaded_from_manifest(tmp_path: Path) -> None:
    module_dir = tmp_path / "sample-module"
    module_dir.mkdir()
    router_file = module_dir / "backend_router.py"
    router_file.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/api/sample-module', tags=['sample-module'])\n"
        "@router.get('/ping')\n"
        "async def ping():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    (module_dir / "manifest.json").write_text(
        json.dumps({
            "key": "sample-module",
            "backend": {"router": "backend_router.py"},
        }),
        encoding="utf-8",
    )

    app = FastAPI()
    register_routers(app, module_paths=(), modules_root=tmp_path)

    assert "/api/sample-module/ping" in app.openapi()["paths"]


def test_module_manifest_without_backend_router_is_not_mounted(tmp_path: Path) -> None:
    module_dir = tmp_path / "frontend-only"
    module_dir.mkdir()
    (module_dir / "manifest.json").write_text(
        json.dumps({"key": "frontend-only", "component_key": "index.vue"}),
        encoding="utf-8",
    )

    assert list(iter_module_router_files(tmp_path)) == []
