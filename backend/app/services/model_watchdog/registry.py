import json
from pathlib import Path
from typing import Literal

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
    ):
        self.name = name
        self.purpose = purpose
        self.endpoint = endpoint
        self.health_path = health_path
        self.model_type = model_type
        self.startup_script = startup_script
        self.port = port
        self.description = description

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
        }


_REGISTRY: dict[str, ModelRecord] = {}

_MODELS_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "backend" / "data" / "config" / "models.json"
)


def _load_from_config() -> None:
    """Load watchdog_models from models.json (single source of truth)."""
    if not _MODELS_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"models.json not found at {_MODELS_CONFIG_PATH}. "
            "Cannot initialize model registry."
        )
    with open(_MODELS_CONFIG_PATH, "r") as f:
        config = json.load(f)

    watchdog_models = config.get("watchdog_models", {})
    if not watchdog_models:
        raise ValueError(
            f"'watchdog_models' section missing or empty in {_MODELS_CONFIG_PATH}"
        )

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
