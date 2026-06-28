"""Success experience injector: match current input against known success paths.

Injects prompt-level workflow advice, not raw payload data.
Contract: inject(messages, diagnosis, current_user_input, owner_id, logger) → (messages, diagnosis)
"""

import logging

from ..experience_memory import format_injection as _experience_format
from ..experience_memory import match_experience as _experience_match


async def inject(
    messages: list[dict],
    diagnosis: dict,
    current_user_input: str,
    owner_id: int,
    logger: logging.Logger = logging.getLogger("v2.agent").getChild("injector.experience"),
) -> tuple[list[dict], dict]:
    """Inject success experience as prompt-level workflow advice."""
    try:
        matched = await _experience_match(current_user_input, limit=2, caller=f"user:{owner_id}")
        injection = _experience_format(matched)
        if injection and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += injection
                    break
            diagnosis["experience_injected"] = [e["id"] for e in matched if e.get("id")]
            diagnosis["experience_injection"] = "成功注入" if injection else "无命中"
        else:
            diagnosis["experience_injection"] = "无命中"
    except Exception as e:
        logger.warning("经验注入失败（降级，不阻塞）: %s", e)
        diagnosis["experience_injection"] = f"降级: {e}"
    return messages, diagnosis
