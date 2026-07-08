from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GenSpec:
    prompt: str
    width: int = 1024
    height: int = 1024
    count: int = 1
    steps: int = 30
    aspect_ratio: str | None = None
    template_config: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


@dataclass
class GenResult:
    image_bytes: bytes | None = None
    image_url: str | None = None
    seed: int | None = None
    meta: dict = field(default_factory=dict)


class ImageProvider(ABC):
    provider_key: str = ""

    @abstractmethod
    async def generate(self, spec: GenSpec) -> list[GenResult]:
        ...

    async def transform(self, spec: GenSpec) -> list[GenResult]:
        raise NotImplementedError(f"{self.provider_key} does not support image-to-image generation")
