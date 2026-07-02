"""Content IR correction loop for Agent.

When the Agent generates a Content IR that fails backend validation,
this module feeds the validation errors back to the LLM for correction,
up to a maximum number of retries.

Usage:
    result = await correct_content_ir(
        original_ir, conversation_id, profile_key, messages, tools
    )
"""
import json
import logging

from ..engine.engine import chat_with_degradation_chain

logger = logging.getLogger("v2.agent").getChild("content_ir_correction")

MAX_RETRIES = 3

CORRECTION_PROMPT = """你刚才输出的 Content IR 不符合后端规范。
请只修正 JSON，不要解释，不要改变用户原始意图，不要增加无关内容。

后端错误：
{validation_errors}

请返回修正后的完整 Content IR JSON。"""


async def validate_and_correct(
    content_ir: dict,
    conversation_id: int,
    profile_key: str,
) -> dict:
    """Validate Content IR and correct if needed.

    Args:
        content_ir: The original Content IR dict from LLM.
        conversation_id: Conversation ID for model call tracing.
        profile_key: Model profile key.

    Returns:
        Dict with keys:
            "success": True if ultimately valid, False otherwise.
            "content_ir": The final (possibly corrected) Content IR.
            "errors": List of validation errors (empty on success).
            "retry_count": How many retries were used.
    """
    from app.services.module_registry import call_capability

    current_ir = dict(content_ir)
    retry_count = 0

    for attempt in range(MAX_RETRIES + 1):
        # Validate
        try:
            result = await call_capability(
                "content", "validate_ir",
                {"content_ir": current_ir},
                "system:agent-engine",
                caller_role="viewer",
            )
        except Exception as e:
            logger.warning("content:validate_ir call failed: %s", e)
            return {
                "success": False,
                "content_ir": current_ir,
                "errors": [{"code": "validate_call_failed", "message": str(e)}],
                "retry_count": retry_count,
            }

        if isinstance(result, dict):
            inner = result.get("data", result)
            errors = inner.get("errors", []) if isinstance(inner, dict) else []
        else:
            errors = []

        if not errors:
            return {
                "success": True,
                "content_ir": current_ir,
                "errors": [],
                "retry_count": retry_count,
            }

        retry_count = attempt

        if attempt >= MAX_RETRIES:
            logger.info("Content IR correction exhausted after %d retries", MAX_RETRIES)
            return {
                "success": False,
                "content_ir": current_ir,
                "errors": errors,
                "retry_count": retry_count,
            }

        # Feed errors back to LLM for correction
        correction_msg = CORRECTION_PROMPT.format(
            validation_errors=json.dumps(errors, ensure_ascii=False, indent=2),
        )

        correction_messages = [
            {"role": "user", "content": json.dumps(current_ir, ensure_ascii=False)},
            {"role": "user", "content": correction_msg},
        ]

        try:
            correction_result = await chat_with_degradation_chain(
                correction_messages,
                profile_key,
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.warning("LLM correction call failed: %s", e)
            return {
                "success": False,
                "content_ir": current_ir,
                "errors": errors,
                "retry_count": retry_count,
            }

        if correction_result.get("error"):
            logger.warning("LLM correction returned error: %s", correction_result["error"])
            return {
                "success": False,
                "content_ir": current_ir,
                "errors": errors,
                "retry_count": retry_count,
            }

        # Parse the corrected IR from LLM response
        corrected_text = correction_result.get("content", "")
        if not corrected_text:
            logger.warning("LLM correction returned empty content")
            continue

        try:
            current_ir = _extract_json(corrected_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("LLM correction returned non-JSON: %s", e)
            continue

        logger.info("Content IR correction attempt %d/%d", attempt + 1, MAX_RETRIES)

    return {
        "success": False,
        "content_ir": current_ir,
        "errors": errors,
        "retry_count": retry_count,
    }


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM response text.

    Tries parsing as-is first; if that fails, looks for ```json ... ``` blocks.
    """
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Look for code blocks
    import re
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Look for anything that looks like a JSON object
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Could not extract JSON from LLM response", text, 0)
