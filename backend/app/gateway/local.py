import asyncio
from typing import AsyncGenerator

from .base import BaseProvider


class LocalProvider(BaseProvider):
    def __init__(self, allow_echo: bool = False) -> None:
        self.allow_echo = allow_echo

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> dict:
        if not self.allow_echo:
            return {
                "error": (
                    "Local echo provider is disabled. Configure a real local "
                    "OpenAI-compatible provider such as llama.cpp or ollama."
                )
            }
        last = messages[-1]["content"] if messages else ""
        return {"content": f"[Local echo] {last[:64]}", "thinking": ""}

    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        if not self.allow_echo:
            yield {
                "type": "error",
                "content": (
                    "Local echo provider is disabled. Configure a real local "
                    "OpenAI-compatible provider such as llama.cpp or ollama."
                ),
            }
            return
        last = messages[-1]["content"] if messages else ""
        words = f"[Local echo] {last[:64]}".split(" ")
        for word in words:
            await asyncio.sleep(0.05)
            yield {"type": "token", "content": word + " "}
        yield {"type": "done", "content": ""}

    async def check_health(self) -> bool:
        return self.allow_echo
