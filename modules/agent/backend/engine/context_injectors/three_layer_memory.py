"""Three-layer memory injector: stable rules + chunk + semantic recall.

Appends relevant memory context to the first system message.
Contract: inject(messages, diagnosis, owner_id, current_user_input, logger) → (messages, diagnosis)
"""

import logging

from ..layered_memory import three_layer_recall as _three_layer_recall


async def inject(
    messages: list[dict],
    diagnosis: dict,
    owner_id: int,
    current_user_input: str,
    logger: logging.Logger = logging.getLogger("v2.agent").getChild("injector.memory"),
) -> tuple[list[dict], dict]:
    """Inject three-layer memory (stable rules + chunks + semantic recall)."""
    try:
        three_layer = await _three_layer_recall(owner_id, current_user_input)
        if three_layer.get("injection") and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += "\n\n---\n\n" + three_layer["injection"]
                    break
            diagnosis["three_layer_memory"] = {
                "stable_rules": len(three_layer.get("stable_rules", [])),
                "chunks": len(three_layer.get("chunks", [])),
                "semantic": len(three_layer.get("semantic", [])),
            }
    except Exception as e:
        logger.warning("三层记忆注入失败（non-fatal）: %s", e)
        diagnosis["three_layer_memory"] = f"降级: {e}"
    return messages, diagnosis
