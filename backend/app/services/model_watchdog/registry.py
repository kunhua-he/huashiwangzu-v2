from typing import Literal

from app.gateway.config import get_models_config_path, get_watchdog_model_configs

ModelType = Literal["local", "cloud"]
ModelPurpose = str  # "embedding" | "rerank" | "vision" | "text" (English, from models.json)


class ModelRecord:
    def __init__(
        self,
        name: str,
        purpose: str,
        endpoint: str,
        health_path: str,
        model_type: ModelType,
        startup_script: str = "",
        port: int = 0,
        description: str = "",
        launch: dict | None = None,
    ):
        self.name = name
        self.purpose = purpose
        self.endpoint = endpoint
        self.health_path = health_path
        self.model_type = model_type
        self.startup_script = startup_script
        self.port = port
        self.description = description
        self.launch = launch or {}

    def health_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/{self.health_path.lstrip('/')}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "endpoint": self.endpoint,
            "health_path": self.health_path,
            "model_type": self.model_type,
            "startup_script": self.startup_script,
            "port": self.port,
            "description": self.description,
            "launch": self.launch,
        }


_REGISTRY: dict[str, ModelRecord] = {}


def _load_from_config() -> None:
    """Load watchdog_models from models.json (single source of truth)."""
    config_path = get_models_config_path()
    if not config_path.exists():
        raise FileNotFoundError(
            f"models.json not found at {config_path}. "
            "Cannot initialize model registry."
        )

    watchdog_models = get_watchdog_model_configs()
    if not watchdog_models:
        raise ValueError(
            f"'watchdog_models' section missing or empty in {config_path}"
        )

    _REGISTRY.clear()
    for name, info in watchdog_models.items():
        record = ModelRecord(
            name=name,
            purpose=info.get("purpose", ""),
            endpoint=info.get("endpoint", ""),
            health_path=info.get("health_path", ""),
            model_type=info.get("model_type", "local"),
            startup_script=info.get("startup_script", ""),
            port=info.get("port", 0),
            description=info.get("description", ""),
            launch=info.get("launch") or {},
        )
        _REGISTRY[name] = record


# Initialize registry from config file at import time
_load_from_config()


def register(record: ModelRecord) -> None:
    _REGISTRY[record.name] = record


def get_model(name: str) -> ModelRecord:
    record = _REGISTRY.get(name)
    if not record:
        raise KeyError(f"Model '{name}' not found in registry")
    return record


def list_models() -> list[ModelRecord]:
    return list(_REGISTRY.values())


def list_local_models() -> list[ModelRecord]:
    return [m for m in _REGISTRY.values() if m.model_type == "local"]
