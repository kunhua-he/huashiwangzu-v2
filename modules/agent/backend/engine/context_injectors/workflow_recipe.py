"""Workflow recipe injector: inject mined per-user shortest-path recipes.

Contract: inject(messages, diagnosis, db, owner_id, current_input) → (messages, diagnosis)
"""

import logging

from ..workflow_recipe_service import format_recipe_for_injection, match_recipes

logger = logging.getLogger("v2.agent").getChild("injector.recipe")


async def inject(
    messages: list[dict],
    diagnosis: dict,
    db,
    owner_id: int,
    current_input: str,
) -> tuple[list[dict], dict]:
    """Match and inject per-user workflow recipes into the first system message."""
    try:
        recipes = await match_recipes(db, owner_id, current_input)
        injection = format_recipe_for_injection(recipes)
        if injection and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += injection
                    break
            diagnosis["recipe_injected"] = len(recipes)
            diagnosis["recipe_labels"] = [r.intent_label for r in recipes]
        else:
            diagnosis["recipe_injected"] = 0
    except Exception as e:
        logger.warning("Recipe injection failed: %s", e)
        diagnosis["recipe_injection_error"] = str(e)
    return messages, diagnosis
