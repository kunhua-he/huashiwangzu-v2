"""FastAPI router for image-gen module.

Multi-provider template adapter architecture.
"""
import io
import json
import logging
import re
import time
import uuid
from pathlib import Path

from app.core.exceptions import AppException, ValidationError
from app.database import AsyncSessionLocal, engine
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_reader import resolve_caller_user_id
from app.services.module_registry import register_capability
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, Text, desc, func, select, text
from sqlalchemy.orm import declarative_base

from .providers import (
    get_default_template,
    get_default_transform_template,
    get_provider,
    list_templates,
    resolve_provider,
)
from .providers.base import GenResult, GenSpec

logger = logging.getLogger("v2.image-gen").getChild("router")

router = APIRouter(prefix="/api/image-gen", tags=["image-gen"])

MIN_IMAGE_DIMENSION = 256
MAX_IMAGE_DIMENSION = 2048
MAX_IMAGE_COUNT = 4
MIN_STEPS = 1
MAX_STEPS = 100

# ---------------------------------------------------------------------------
# imagegen_records table (lightweight cost tracking)
# ---------------------------------------------------------------------------

_Base = declarative_base()


class ImageGenRecord(_Base):
    __tablename__ = "imagegen_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False, index=True)
    template = Column(Text, nullable=False)
    provider = Column(Text, nullable=True)
    request_id = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    image_count = Column(Integer, nullable=False, default=0)
    points_cost = Column(Integer, nullable=True)
    balance_after = Column(Integer, nullable=True)
    file_ids = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="success")
    error_msg = Column(Text, nullable=True)
    degraded_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


def _ensure_tables():
    import asyncio

    async def _init():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(_Base.metadata.create_all)
                existing = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'imagegen_records'
                """))
                existing_columns = {row[0] for row in existing}
                extra_columns = {
                    "provider": "TEXT",
                    "request_id": "TEXT",
                    "degraded_reason": "TEXT",
                }
                for column_name, column_type in extra_columns.items():
                    if column_name not in existing_columns:
                        await conn.execute(text(
                            f"ALTER TABLE imagegen_records ADD COLUMN {column_name} {column_type}"
                        ))
            logger.info("imagegen_records table ensured")
        except Exception as e:
            logger.warning("Failed to ensure imagegen_records table: %s", e)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        asyncio.ensure_future(_init())
    else:
        try:
            asyncio.run(_init())
        except Exception as e:
            logger.warning("Startup init failed: %s", e)


_ensure_tables()

# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

async def _translate_to_english(chinese_prompt: str) -> str:
    from app.gateway.router import gateway_router

    messages = [
        {
            "role": "system",
            "content": "You are an AI painting prompt translator. Translate the user's Chinese requirement into a concise English painting prompt. Output ONLY the English prompt, no explanations, no prefixes.",
        },
        {"role": "user", "content": chinese_prompt},
    ]
    try:
        result = await gateway_router.chat(messages, profile_key="deepseek-v4-flash")
        content = result.get("content", "").strip()
        if content:
            logger.info("Translated prompt: %r -> %r", chinese_prompt[:60], content[:120])
            return content
    except Exception as e:
        logger.warning("Prompt translation failed: %s", e)
    return chinese_prompt


def _parse_bounded_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _parse_bounded_float(value: object, field_name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _dimensions_from_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    normalized = aspect_ratio.strip().lower()
    aspect_map = {
        "square": (1024, 1024),
        "portrait": (768, 1024),
        "landscape": (1280, 720),
        "1:1": (1024, 1024),
        "3:4": (768, 1024),
        "16:9": (1280, 720),
    }
    if normalized in aspect_map:
        return aspect_map[normalized]

    if ":" not in normalized:
        raise ValidationError("Invalid aspect_ratio; expected square, portrait, landscape, or W:H")
    try:
        raw_w, raw_h = normalized.split(":", 1)
        ratio_w, ratio_h = float(raw_w), float(raw_h)
    except ValueError as exc:
        raise ValidationError("Invalid aspect_ratio; expected numeric W:H") from exc
    if ratio_w <= 0 or ratio_h <= 0:
        raise ValidationError("Invalid aspect_ratio; values must be positive")

    if ratio_w >= ratio_h:
        width = 1024
        height = round(width * ratio_h / ratio_w)
    else:
        height = 1024
        width = round(height * ratio_w / ratio_h)
    width = max(MIN_IMAGE_DIMENSION, min(MAX_IMAGE_DIMENSION, width))
    height = max(MIN_IMAGE_DIMENSION, min(MAX_IMAGE_DIMENSION, height))
    return width, height


async def _load_source_image(source_file_id: int, user_id: int) -> dict:
    from app.services.file_service import check_file_access
    from app.services.file_upload_service import UPLOAD_ROOT

    async with AsyncSessionLocal() as db:
        file = await check_file_access(db, source_file_id, user_id)
        ext = (file.extension or "").lower()
        mime_type = file.mime_type or f"image/{ext or 'png'}"
        if not (mime_type.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp"}):
            raise ValidationError("source_file_id must point to an image file")
        source_path = (UPLOAD_ROOT / file.storage_path).resolve()
        upload_root = UPLOAD_ROOT.resolve()
        if not source_path.is_relative_to(upload_root) or not source_path.is_file():
            raise ValidationError("source image file is unavailable")
        image_bytes = source_path.read_bytes()
        if not image_bytes:
            raise ValidationError("source image file is empty")
        filename = f"{file.name}.{ext}" if ext else file.name
        return {
            "file_id": source_file_id,
            "filename": filename,
            "mime_type": mime_type,
            "bytes": image_bytes,
            "size": len(image_bytes),
        }


async def _persist_provider_results(
    gen_results: list[GenResult],
    user_id: int,
    is_placeholder: bool,
    filename_prefix: str = "image-gen",
    placeholder_explanation: str = "占位图，真实生成待接入",
    publish: bool = False,
) -> tuple[list[dict], list[int], list[str], bool]:
    from app.core.workspace_security import ensure_user_workspace

    ts = int(time.time() * 1000)
    request_suffix = uuid.uuid4().hex[:8]
    results = []
    file_ids: list[int] = []
    persist_errors: list[str] = []
    generated_placeholder = is_placeholder
    async with AsyncSessionLocal() as db:
        for idx, gen_result in enumerate(gen_results):
            image_bytes = gen_result.image_bytes
            result_placeholder = is_placeholder or bool(gen_result.meta.get("placeholder"))
            generated_placeholder = generated_placeholder or result_placeholder

            if image_bytes is None and gen_result.image_url:
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                        resp = await client.get(gen_result.image_url)
                        resp.raise_for_status()
                        image_bytes = resp.content
                except Exception as e:
                    err = f"download failed for image {idx + 1}: {e}"
                    persist_errors.append(err)
                    logger.warning("Failed to download image from URL %s: %s", gen_result.image_url, e)
                    continue

            if image_bytes is None:
                persist_errors.append(f"image {idx + 1} returned no bytes or URL")
                continue

            filename = f"{filename_prefix}_{ts}_{request_suffix}_{idx + 1}.png"
            try:
                if publish:
                    from app.services.file_upload_service import upload_file

                    file_obj = io.BytesIO(image_bytes)
                    upload_result = await upload_file(
                        db, file_obj, filename, user_id, folder_id=None,
                    )
                    file_ids.append(upload_result["id"])
                    entry: dict = {
                        "type": "image",
                        "file_id": upload_result["id"],
                        "name": upload_result["name"],
                        "size": upload_result["size"],
                        "placeholder": result_placeholder,
                        "published": True,
                    }
                else:
                    workspace = ensure_user_workspace(user_id)
                    output_dir = workspace / "image-gen"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = (output_dir / Path(filename).name).resolve()
                    output_path.write_bytes(image_bytes)
                    entry = {
                        "type": "image",
                        "workspace_path": str(output_path.relative_to(workspace.resolve())),
                        "name": filename,
                        "size": output_path.stat().st_size,
                        "placeholder": result_placeholder,
                        "published": False,
                        "note": "Use terminal-tools:publish to deliver to desktop",
                    }
            except Exception as e:
                err = f"save failed for image {idx + 1}: {e}"
                persist_errors.append(err)
                logger.warning("Failed to save generated image %d: %s", idx + 1, e)
                continue
            if result_placeholder:
                entry["explanation"] = placeholder_explanation
            results.append(entry)

    return results, file_ids, persist_errors, generated_placeholder


def _generation_resource_refs(
    *,
    request_id: str,
    record_id: int | None,
    images: list[dict],
) -> list[dict]:
    refs: list[dict] = []
    if record_id is not None:
        refs.append({
            "type": "record",
            "id": record_id,
            "display_name": f"Image generation record {record_id}",
            "access_scope": "user",
            "provenance": {"module": "image-gen", "request_id": request_id},
        })
    for index, image in enumerate(images, start=1):
        file_id = image.get("file_id")
        if file_id is not None:
            refs.append({
                "type": "file",
                "id": int(file_id),
                "locator": f"/api/files/detail/{int(file_id)}",
                "mime_type": "image/png",
                "display_name": str(image.get("name") or f"Generated image {index}"),
                "access_scope": "user",
                "provenance": {"module": "image-gen", "request_id": request_id},
            })
            continue
        relative_locator = str(image.get("workspace_path") or "")
        refs.append({
            "type": "artifact",
            "id": f"{request_id}:{index}",
            "locator": relative_locator,
            "mime_type": "image/png",
            "display_name": str(image.get("name") or f"Generated image {index}"),
            "access_scope": "user",
            "provenance": {"module": "image-gen", "request_id": request_id},
        })
    return refs


def _resolve_dimensions(size: str, aspect_ratio: str | None) -> tuple[int, int]:
    if aspect_ratio:
        return _dimensions_from_aspect_ratio(aspect_ratio)

    match = re.match(r"^(\d+)\s*[xX]\s*(\d+)$", size)
    if not match:
        raise ValidationError("Invalid size format; expected e.g. 1024x1024, or provide aspect_ratio")

    width, height = int(match.group(1)), int(match.group(2))
    if (
        width < MIN_IMAGE_DIMENSION
        or width > MAX_IMAGE_DIMENSION
        or height < MIN_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
    ):
        raise ValidationError(
            f"size dimensions must be between {MIN_IMAGE_DIMENSION} and {MAX_IMAGE_DIMENSION}"
        )
    return width, height


# ---------------------------------------------------------------------------
# Core capability: generate
# ---------------------------------------------------------------------------

async def _generate(params: dict, caller: str) -> dict:
    prompt = str(params.get("prompt", "")).strip()
    size = str(params.get("size", "1024x1024")).strip()
    aspect_ratio = str(params.get("aspect_ratio", "")).strip() or None
    count = _parse_bounded_int(params.get("count", 1), "count", 1, MAX_IMAGE_COUNT)
    steps = _parse_bounded_int(params.get("steps", 30), "steps", MIN_STEPS, MAX_STEPS)
    template_key = str(params.get("template", "")).strip() or get_default_template()
    request_id = uuid.uuid4().hex

    if not prompt:
        raise ValidationError("prompt is required")

    user_id = resolve_caller_user_id(caller)
    publish = _parse_bool(params.get("publish"), default=False)
    width, height = _resolve_dimensions(size, aspect_ratio)

    try:
        provider, template_cfg, is_placeholder = resolve_provider(template_key)
    except ValueError:
        raise ValidationError(f"Unknown template: {template_key}")
    requested_provider = str(template_cfg.get("provider", ""))
    provider_key = provider.provider_key
    degraded_reason = None
    if is_placeholder and requested_provider != "placeholder":
        degraded_reason = f"{requested_provider} provider is not configured; downgraded to placeholder"
    elif is_placeholder:
        degraded_reason = "placeholder template selected"

    if not is_placeholder:
        prompt_language = template_cfg.get("prompt_language", "any")
        if prompt_language == "en" and any(ord(c) > 127 for c in prompt):
            translated = await _translate_to_english(prompt)
            if translated != prompt:
                logger.info("Prompt auto-translated from Chinese to English")
            prompt = translated

    spec = GenSpec(
        prompt=prompt,
        width=width,
        height=height,
        count=count,
        steps=steps,
        aspect_ratio=aspect_ratio,
        template_config=template_cfg,
    )

    try:
        gen_results = await provider.generate(spec)
    except NotImplementedError:
        fallback_provider = get_provider("placeholder")
        gen_results = await fallback_provider.generate(spec)
        is_placeholder = True
        provider_key = fallback_provider.provider_key
        degraded_reason = f"{requested_provider} provider is not implemented; downgraded to placeholder"
        logger.info("Fell back to placeholder for template=%s", template_key)
    except RuntimeError as e:
        error_msg = str(e)
        logger.error("Image generation failed for template=%s: %s", template_key, error_msg)
        friendly = "生图失败，请稍后重试"
        if any(kw in error_msg.lower() for kw in ("timeout", "timed out", "time out")):
            friendly = "生图超时，请稍后重试"
        elif any(kw in error_msg.lower() for kw in ("rate limit", "rate_limit", "too many")):
            friendly = "生图请求过于频繁，请稍后重试"
        elif any(kw in error_msg.lower() for kw in ("auth", "key", "credential", "unauthorized")):
            friendly = "生图服务认证失败，请联系管理员"

        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError(friendly) from e
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unexpected error in image generation: %s", error_msg)
        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError("生图异常，请稍后重试") from e

    results, file_ids, persist_errors, generated_placeholder = await _persist_provider_results(
        gen_results,
        user_id,
        is_placeholder,
        filename_prefix="image-gen",
        placeholder_explanation="占位图，真实生成待接入",
        publish=publish,
    )

    if not results:
        error_msg = "; ".join(persist_errors) or "image generation produced no downloadable images"
        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError("生图失败：未生成可用图片")

    points_cost = None
    balance = None
    if gen_results and gen_results[0].meta:
        points_cost = gen_results[0].meta.get("points_cost")
        balance = gen_results[0].meta.get("balance")

    if generated_placeholder and degraded_reason is None:
        degraded_reason = "placeholder generation path"
    status = "partial" if persist_errors else ("degraded" if generated_placeholder else "success")
    record_id = await _save_record(
        owner_id=user_id, template=template_key, prompt=spec.prompt,
        image_count=len(results), file_ids=file_ids,
        status=status,
        error_msg="; ".join(persist_errors) if persist_errors else None,
        points_cost=points_cost, balance_after=balance,
        provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
    )

    response = {
        "task": {"request_id": request_id, "record_id": record_id},
        "images": results,
        "placeholder": generated_placeholder,
        "degraded": generated_placeholder,
        "status": status,
        "template": template_key,
        "provider": provider_key,
        "requested_provider": requested_provider,
        "degraded_reason": degraded_reason,
        "points_cost": points_cost,
        "balance": balance,
        "published": publish,
    }
    response["resource_refs"] = _generation_resource_refs(
        request_id=request_id,
        record_id=record_id,
        images=results,
    )
    if persist_errors:
        response["error"] = "部分图片保存失败，已返回可用结果"
        response["detail"] = "; ".join(persist_errors)
    return response


# ---------------------------------------------------------------------------
# Core capability: transform (image-to-image)
# ---------------------------------------------------------------------------

async def _transform(params: dict, caller: str) -> dict:
    source_raw = params.get("source_file_id")
    if source_raw is None:
        source_raw = params.get("image_file_id")
    if source_raw is None:
        source_raw = params.get("file_id")
    source_file_id = _parse_bounded_int(source_raw, "source_file_id", 1, 2_147_483_647)
    prompt = str(params.get("prompt", "")).strip()
    size = str(params.get("size", "1024x1024")).strip()
    aspect_ratio = str(params.get("aspect_ratio", "")).strip() or None
    count = _parse_bounded_int(params.get("count", 1), "count", 1, MAX_IMAGE_COUNT)
    steps = _parse_bounded_int(params.get("steps", 30), "steps", MIN_STEPS, MAX_STEPS)
    strength = _parse_bounded_float(params.get("strength", 0.7), "strength", 0.0, 1.0)
    mode = str(params.get("mode", "edit")).strip() or "edit"
    preserve_subject = _parse_bool(params.get("preserve_subject"), default=True)
    template_key = str(params.get("template", "")).strip() or get_default_transform_template()
    request_id = uuid.uuid4().hex

    if not prompt:
        raise ValidationError("prompt is required")

    user_id = resolve_caller_user_id(caller)
    publish = _parse_bool(params.get("publish"), default=False)
    width, height = _resolve_dimensions(size, aspect_ratio)
    source_image = await _load_source_image(source_file_id, user_id)

    try:
        provider, template_cfg, is_placeholder = resolve_provider(template_key)
    except ValueError:
        raise ValidationError(f"Unknown template: {template_key}")
    requested_provider = str(template_cfg.get("provider", ""))
    provider_key = provider.provider_key
    degraded_reason = None
    if is_placeholder and requested_provider != "placeholder":
        degraded_reason = f"{requested_provider} provider is not configured; downgraded to placeholder"
    elif is_placeholder:
        degraded_reason = "placeholder template selected"

    if not is_placeholder:
        prompt_language = template_cfg.get("prompt_language", "any")
        if prompt_language == "en" and any(ord(c) > 127 for c in prompt):
            translated = await _translate_to_english(prompt)
            if translated != prompt:
                logger.info("Transform prompt auto-translated from Chinese to English")
            prompt = translated

    spec = GenSpec(
        prompt=prompt,
        width=width,
        height=height,
        count=count,
        steps=steps,
        aspect_ratio=aspect_ratio,
        template_config=template_cfg,
        extra={
            "source_image": source_image,
            "mode": mode,
            "strength": strength,
            "preserve_subject": preserve_subject,
        },
    )

    try:
        gen_results = await provider.transform(spec)
    except NotImplementedError:
        fallback_provider = get_provider("placeholder")
        gen_results = await fallback_provider.transform(spec)
        is_placeholder = True
        provider_key = fallback_provider.provider_key
        degraded_reason = f"{requested_provider} provider does not support image-to-image; downgraded to placeholder"
        logger.info("Fell back to placeholder transform for template=%s", template_key)
    except RuntimeError as e:
        error_msg = str(e)
        logger.error("Image transform failed for template=%s: %s", template_key, error_msg)
        friendly = "图生图失败，请稍后重试"
        if any(kw in error_msg.lower() for kw in ("timeout", "timed out", "time out")):
            friendly = "图生图超时，请稍后重试"
        elif any(kw in error_msg.lower() for kw in ("rate limit", "rate_limit", "too many")):
            friendly = "图生图请求过于频繁，请稍后重试"
        elif any(kw in error_msg.lower() for kw in ("auth", "key", "credential", "unauthorized")):
            friendly = "图生图服务认证失败，请联系管理员"

        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError(friendly) from e
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unexpected error in image transform: %s", error_msg)
        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError("图生图异常，请稍后重试") from e

    results, file_ids, persist_errors, generated_placeholder = await _persist_provider_results(
        gen_results,
        user_id,
        is_placeholder,
        filename_prefix="image-transform",
        placeholder_explanation="占位图，真实图生图待接入",
        publish=publish,
    )

    if not results:
        error_msg = "; ".join(persist_errors) or "image transform produced no downloadable images"
        await _save_record(
            owner_id=user_id, template=template_key, prompt=spec.prompt,
            image_count=0, file_ids=None, status="failed", error_msg=error_msg,
            provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
        )
        raise ValidationError("图生图失败：未生成可用图片")

    points_cost = None
    balance = None
    if gen_results and gen_results[0].meta:
        points_cost = gen_results[0].meta.get("points_cost")
        balance = gen_results[0].meta.get("balance")

    if generated_placeholder and degraded_reason is None:
        degraded_reason = "placeholder transform path"
    status = "partial" if persist_errors else ("degraded" if generated_placeholder else "success")
    record_id = await _save_record(
        owner_id=user_id, template=template_key, prompt=spec.prompt,
        image_count=len(results), file_ids=file_ids,
        status=status,
        error_msg="; ".join(persist_errors) if persist_errors else None,
        points_cost=points_cost, balance_after=balance,
        provider=provider_key, request_id=request_id, degraded_reason=degraded_reason,
    )

    response = {
        "task": {"request_id": request_id, "record_id": record_id},
        "images": results,
        "placeholder": generated_placeholder,
        "degraded": generated_placeholder,
        "status": status,
        "template": template_key,
        "provider": provider_key,
        "requested_provider": requested_provider,
        "degraded_reason": degraded_reason,
        "points_cost": points_cost,
        "balance": balance,
        "source_file_id": source_file_id,
        "mode": mode,
        "strength": strength,
        "published": publish,
    }
    response["resource_refs"] = _generation_resource_refs(
        request_id=request_id,
        record_id=record_id,
        images=results,
    )
    if persist_errors:
        response["error"] = "部分图片保存失败，已返回可用结果"
        response["detail"] = "; ".join(persist_errors)
    return response


async def _save_record(
    owner_id: int, template: str, prompt: str,
    image_count: int, file_ids: list[int] | None,
    status: str, error_msg: str | None = None,
    points_cost: int | None = None, balance_after: int | None = None,
    provider: str | None = None, request_id: str | None = None,
    degraded_reason: str | None = None,
) -> int | None:
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import insert
            stmt = insert(ImageGenRecord).values(
                owner_id=owner_id,
                template=template,
                provider=provider,
                request_id=request_id,
                prompt=prompt[:500],
                image_count=image_count,
                file_ids=json.dumps(file_ids) if file_ids else None,
                status=status,
                error_msg=error_msg,
                degraded_reason=degraded_reason,
                points_cost=points_cost,
                balance_after=balance_after,
            ).returning(ImageGenRecord.id)
            result = await db.execute(stmt)
            await db.commit()
            return result.scalar_one_or_none()
    except Exception as e:
        logger.warning("Failed to save imagegen record: %s", e)
        return None


# ---------------------------------------------------------------------------
# Capability: list_templates
# ---------------------------------------------------------------------------

async def _list_templates(params: dict, caller: str) -> dict:
    templates = list_templates()
    return {"templates": templates}


# ---------------------------------------------------------------------------
# Capability: usage_history
# ---------------------------------------------------------------------------

async def _usage_history(params: dict, caller: str) -> dict:
    user_id = resolve_caller_user_id(caller)
    limit = min(int(params.get("limit", 20)), 100)
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ImageGenRecord)
                .where(ImageGenRecord.owner_id == user_id)
                .order_by(desc(ImageGenRecord.id))
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            records = []
            for r in rows:
                file_ids = []
                if r.file_ids:
                    try:
                        parsed = json.loads(r.file_ids)
                        if isinstance(parsed, list):
                            file_ids = [int(item) for item in parsed]
                    except (TypeError, ValueError, json.JSONDecodeError):
                        file_ids = []
                records.append({
                    "id": r.id,
                    "request_id": r.request_id,
                    "template": r.template,
                    "provider": r.provider,
                    "prompt": r.prompt,
                    "image_count": r.image_count,
                    "file_ids": file_ids,
                    "points_cost": r.points_cost,
                    "balance_after": r.balance_after,
                    "status": r.status,
                    "error_msg": r.error_msg,
                    "degraded_reason": r.degraded_reason,
                    "created_at": str(r.created_at) if r.created_at else None,
                })
            return {"records": records}
    except Exception as e:
        logger.warning("Failed to query usage history: %s", e)
        raise AppException("生图历史查询失败") from e


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    aspect_ratio: str | None = None
    count: int = 1
    steps: int = 30
    template: str = ""
    publish: bool = True


class TransformRequest(BaseModel):
    source_file_id: int
    prompt: str
    size: str = "1024x1024"
    aspect_ratio: str | None = None
    count: int = 1
    steps: int = 30
    template: str = ""
    mode: str = "edit"
    strength: float = 0.7
    preserve_subject: bool = True
    publish: bool = True


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "image-gen", "status": "ok"})


@router.post("/generate")
async def call_generate(
    payload: GenerateRequest,
    user: User = Depends(require_permission("editor")),
):
    result = await _generate(payload.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


@router.post("/transform")
async def call_transform(
    payload: TransformRequest,
    user: User = Depends(require_permission("editor")),
):
    result = await _transform(payload.model_dump(), f"user:{user.id}")
    return ApiResponse(data=result)


@router.get("/templates")
async def call_list_templates(
    user: User = Depends(require_permission("viewer")),
):
    result = await _list_templates({}, f"user:{user.id}")
    return ApiResponse(data=result)


@router.get("/history")
async def call_usage_history(
    limit: int = 20,
    user: User = Depends(require_permission("editor")),
):
    result = await _usage_history({"limit": limit}, f"user:{user.id}")
    return ApiResponse(data=result)


# ---------------------------------------------------------------------------
# Register capabilities (Agent discovers these automatically)
# ---------------------------------------------------------------------------

register_capability(
    "image-gen", "generate", _generate,
    description="生成图片：根据提示词生成产品图、海报、配图等（多服务商模板，支持LiblibAI星流/GPTStore/占位图降级）",
    brief="按提示词生成图片",
    parameters={
        "prompt": {"type": "string", "description": "提示词，描述想要生成的图片内容。支持中文（会自动翻译成英文提示词）"},
        "size": {"type": "string", "description": "尺寸，格式如 1024x1024", "default": "1024x1024"},
        "aspect_ratio": {"type": "string", "description": "宽高比，可选 square/portrait/landscape 或如 16:9, 3:4", "default": ""},
        "count": {"type": "integer", "description": "生成数量（1-4）", "default": 1},
        "steps": {"type": "integer", "description": "采样步数", "default": 30},
        "template": {"type": "string", "description": "模板key，可选值由list_templates给出，缺省用默认模板", "default": ""},
        "publish": {"type": "boolean", "description": "是否直接发布到桌面文件系统；Agent默认false，需显式publish才用户可见", "default": False},
    },
    min_role="editor",
    execution_contract={
        "output_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "object"},
                "images": {"type": "array"},
                "resource_refs": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["task", "images", "resource_refs"],
        },
        "execution_mode": "sync",
        "resource_class": "long",
        "timeout_seconds": 600,
        "max_attempts": 1,
        "idempotency": "none",
        "side_effect_level": "create",
        "output_reference_types": ["file", "artifact", "record"],
        "parallel_safe": False,
    },
    retrieval={
        "aliases": ["生图", "生成图片", "制作海报", "产品配图"],
        "when_to_use": "用户明确要求创建新的图片、海报、产品图或视觉素材时",
        "when_not_to_use": "用户要求分析、识别或读取已有图片时",
        "input_reference_types": [],
    },
)

register_capability(
    "image-gen", "transform", _transform,
    description="图生图：读取已有图片file_id作为参考图，按提示词编辑、变体或风格化生成新图片",
    brief="按参考图生成新图片",
    parameters={
        "source_file_id": {"type": "integer", "description": "源图片文件ID，必须是当前用户可访问的图片文件"},
        "prompt": {"type": "string", "description": "图生图提示词，说明要保留、修改或增强的内容"},
        "size": {"type": "string", "description": "输出尺寸，格式如 1024x1024", "default": "1024x1024"},
        "aspect_ratio": {"type": "string", "description": "输出宽高比，可选 square/portrait/landscape 或如 16:9, 3:4", "default": ""},
        "count": {"type": "integer", "description": "生成数量（1-4）", "default": 1},
        "steps": {"type": "integer", "description": "采样步数，部分服务商可能忽略", "default": 30},
        "template": {"type": "string", "description": "模板key，缺省优先使用支持图生图的GPTStore模板", "default": ""},
        "mode": {"type": "string", "description": "模式，如 edit/variation/style_transfer/product_render", "default": "edit"},
        "strength": {"type": "number", "description": "修改强度，0到1，值越大改动越明显", "default": 0.7},
        "preserve_subject": {"type": "boolean", "description": "是否尽量保留主体、产品形态和可读标签", "default": True},
        "publish": {"type": "boolean", "description": "是否直接发布到桌面文件系统；Agent默认false，需显式publish才用户可见", "default": False},
    },
    min_role="editor",
    execution_contract={
        "output_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "object"},
                "images": {"type": "array"},
                "resource_refs": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["task", "images", "resource_refs"],
        },
        "execution_mode": "sync",
        "resource_class": "long",
        "timeout_seconds": 600,
        "max_attempts": 1,
        "idempotency": "none",
        "side_effect_level": "create",
        "output_reference_types": ["file", "artifact", "record"],
        "parallel_safe": False,
    },
    retrieval={
        "aliases": ["图生图", "编辑图片", "图片变体", "风格转换"],
        "when_to_use": "用户要求基于已有图片进行编辑、变体或风格化时",
        "when_not_to_use": "用户只需要识别或分析已有图片时",
        "input_reference_types": ["file"],
    },
)

register_capability(
    "image-gen", "list_templates", _list_templates,
    description="列出可用生图模板（服务商+模型），含凭据是否齐全标识",
    brief="列出可用生图模板",
    parameters={},
    min_role="viewer",
)

register_capability(
    "image-gen", "usage_history", _usage_history,
    description="查询本人的生图历史记录，含积分消耗",
    brief="生图历史记录",
    parameters={
        "limit": {"type": "integer", "description": "返回条数", "default": 20},
    },
    min_role="editor",
)
