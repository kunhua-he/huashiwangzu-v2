from collections.abc import Awaitable, Callable

from typing import Protocol


class _PromptLogger(Protocol):
    def warning(self, message: str, *args, **kwargs) -> None: ...


async def load_prompt_with_fallback(
    db,
    key: str,
    owner_id: int,
    get_prompt: Callable[[object, str, int], Awaitable[str | None]],
    fallbacks: dict[str, str],
    logger: _PromptLogger | None = None,
    **format_kwargs,
) -> str:
    content = await get_prompt(db, key, owner_id)
    if not content:
        content = fallbacks.get(key, "")
    if format_kwargs:
        try:
            content = content.format(**format_kwargs)
        except KeyError as exc:
            if logger:
                logger.warning("Prompt format missing key: %s (prompt=%s, kwargs=%s)", exc, key, format_kwargs)
    return content
