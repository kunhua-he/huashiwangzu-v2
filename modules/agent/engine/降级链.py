"""模型降级链：主模型失败后按 fallback_chain 依次尝试，本地兜底作链尾。

每次降级写日志。流式：首包/探测失败可降级；已开始流式中途断，给清晰错误。"""
import json
import logging
from typing import AsyncGenerator
from app.gateway.router import gateway_router, MODEL_PROFILES, _load_models_config

logger = logging.getLogger("v2.agent.engine.降级链")

_config = _load_models_config()
FALLBACK_CHAIN: list[str] = _config.get("model_types", {}).get("llm", {}).get("fallback_chain", [])


async def chat_with_fallback(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
) -> dict:
    original_key = profile_key
    tried = []
    chain = [profile_key] + [k for k in FALLBACK_CHAIN if k != profile_key]

    for idx, key in enumerate(chain):
        if key in tried:
            continue
        profile = MODEL_PROFILES.get(key)
        if not profile:
            logger.warning("降级链: %s 在 models.json 中不存在，跳过", key)
            continue
        try:
            result = await gateway_router.chat(messages=messages, profile_key=key, tools=tools)
            if result.get("error"):
                exc_text = str(result.get("content", result.get("error", "")))
                raise RuntimeError(exc_text)
            if idx > 0:
                logger.info("降级: %s → %s 成功", original_key if idx == 0 else chain[idx - 1], key)
            return result
        except Exception as e:
            tried.append(key)
            reason = _extract_reason(e)
            if idx < len(chain) - 1:
                next_key = chain[idx + 1]
                logger.warning("降级: %s → %s 原因:%s", key, next_key, reason)
            else:
                logger.error("降级链耗尽: 所有 %d 个模型均失败, 末次原因:%s", len(chain), reason)
                return {"error": str(e), "content": f"(模型调用失败，降级链已耗尽：{reason})"}
    return {"error": "No valid model in fallback chain", "content": "(降级链为空)"}


def _extract_reason(exc: Exception) -> str:
    detail = str(exc)
    if hasattr(exc, "response"):
        try:
            body = exc.response.text
            if body:
                detail = f"{detail[:200]} | 响应体:{body[:500]}"
        except Exception:
            pass
    return detail[:300]


async def chat_stream_with_fallback(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    original_key = profile_key
    chain = [profile_key] + [k for k in FALLBACK_CHAIN if k != profile_key]

    for idx, key in enumerate(chain):
        profile = MODEL_PROFILES.get(key)
        if not profile:
            continue
        try:
            is_first = idx == 0
            async for event in gateway_router.chat_stream(messages=messages, profile_key=key, tools=tools):
                if event.get("type") == "error":
                    raise RuntimeError(event.get("content", ""))
                yield event
            if not is_first:
                logger.info("流式降级: %s → %s 成功", original_key if idx == 0 else chain[idx - 1], key)
            return
        except Exception as e:
            reason = _extract_reason(e)
            if idx < len(chain) - 1:
                next_key = chain[idx + 1]
                logger.warning("流式降级: %s → %s 原因:%s", key, next_key, reason)
                if idx == 0:
                    yield {"type": "degradation", "content": f"降级: {key} → {next_key} 原因:{reason}"}
            else:
                logger.error("流式降级链耗尽: %s", reason)
                yield {"type": "error", "content": f"模型调用失败，降级链已耗尽：{reason}"}
                return
