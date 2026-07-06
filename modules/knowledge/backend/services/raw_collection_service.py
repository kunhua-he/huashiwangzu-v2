"""原始层多轮采集服务。

对文档每页执行三轮独立采集（文本提取 / 截图OCR / 视觉构成），
每轮结果各自落盘到 kb_raw_data，落盘后只读不可变。

并发策略：5 门池摊平任务。将所有 (page, round) 摊平成独立任务，
固定 5 并发门池跑，每任务独立 DB 会话 + 独立 commit，
进度三行各自按真实速度前进。

Round-2 OCR 增强：在 VLM OCR 之外，若 tesseract 可用则额外提取词级
坐标落盘到 metadata_json.words，供 pdf-viewer 叠扫描件文字层。
"""
import asyncio
import hashlib
import io
import logging
from time import perf_counter

from app.database import AsyncSessionLocal
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..ir_models import to_legacy_dict
from ..models import KbDocument, KbRawData
from .model_routing import (
    knowledge_model_call_slot,
    resolve_knowledge_concurrency,
    resolve_knowledge_image_preprocess_int,
    resolve_knowledge_vision_profile,
)
from .parsing_service import IMAGE_FORMATS, parse_document
from .pdf_render_service import get_pdf_page_count, render_page_to_image
from .prompt_utils import TRAW_OCR, TRAW_VISION, load_prompt

logger = logging.getLogger("v2.knowledge").getChild("raw_collection")

# tesseract 可用性检测
TESSERACT_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    logger.info("pytesseract not installed; round-2 word coordinates disabled")

def _tesseract_has_binary() -> bool:
    import shutil
    return shutil.which("tesseract") is not None

def _ocr_words_tesseract(img_bytes: bytes) -> dict | None:
    """用 tesseract 提取词级坐标。返回 {"img_w","img_h","words"} 或 None。"""
    if not TESSERACT_AVAILABLE:
        return None
    if not _tesseract_has_binary():
        logger.info("tesseract binary not found; skip word coordinates")
        return None
    try:
        img = Image.open(io.BytesIO(img_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang="chi_sim+eng")
        img_w, img_h = img.size
        words = []
        for i in range(len(data["text"])):
            t = (data["text"][i] or "").strip()
            if not t:
                continue
            words.append({
                "t": t,
                "x": int(data["left"][i]),
                "y": int(data["top"][i]),
                "w": int(data["width"][i]),
                "h": int(data["height"][i]),
            })
        logger.info("tesseract extracted %d words for image (%dx%d)", len(words), img_w, img_h)
        return {"img_w": img_w, "img_h": img_h, "words": words}
    except Exception as e:
        logger.warning("tesseract OCR failed: %s", e)
        return None


async def _ocr_words_tesseract_async(img_bytes: bytes) -> dict | None:
    """Run blocking tesseract OCR off the worker event loop."""
    prepared, preprocess = _prepare_image_bytes_for_local_ocr(img_bytes)
    result = await asyncio.to_thread(_ocr_words_tesseract, prepared)
    if result is not None:
        result["preprocess"] = preprocess
    return result

# 并发上限对齐 gate_pool.PER_GATE_MAX_CONCURRENT=5
RAW_COLLECT_CONCURRENCY = 5
DEFAULT_LOCAL_OCR_MAX_SIDE = 1600
DEFAULT_LOCAL_OCR_MAX_BYTES = 1_048_576
DEFAULT_LOCAL_OCR_JPEG_QUALITY_START = 84
DEFAULT_LOCAL_OCR_JPEG_QUALITY_FLOOR = 72
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt"}

def _hash_content(content: str) -> str:
    return hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()


def _strip_png_text_chunks(img_bytes: bytes) -> tuple[bytes, dict]:
    diagnostics = {
        "stripped": False,
        "removed_chunks": 0,
        "removed_bytes": 0,
        "original_bytes": len(img_bytes),
        "prepared_bytes": len(img_bytes),
    }
    if not img_bytes.startswith(PNG_SIGNATURE):
        return img_bytes, diagnostics
    output = bytearray(PNG_SIGNATURE)
    offset = len(PNG_SIGNATURE)
    try:
        while offset + 12 <= len(img_bytes):
            chunk_start = offset
            length = int.from_bytes(img_bytes[offset:offset + 4], "big")
            chunk_type = img_bytes[offset + 4:offset + 8]
            chunk_end = offset + 12 + length
            if chunk_end > len(img_bytes):
                return img_bytes, {**diagnostics, "error": "malformed_png_chunk"}
            if chunk_type in PNG_TEXT_CHUNKS:
                diagnostics["stripped"] = True
                diagnostics["removed_chunks"] += 1
                diagnostics["removed_bytes"] += chunk_end - chunk_start
            else:
                output.extend(img_bytes[chunk_start:chunk_end])
            offset = chunk_end
            if chunk_type == b"IEND":
                break
    except Exception as exc:
        return img_bytes, {**diagnostics, "error": str(exc)}
    prepared = bytes(output)
    diagnostics["prepared_bytes"] = len(prepared)
    return prepared, diagnostics


def _prepare_image_bytes_for_local_ocr(img_bytes: bytes) -> tuple[bytes, dict]:
    """Resize/re-encode local OCR input so huge images do not monopolize a worker lane."""
    metadata = {
        "original_bytes": len(img_bytes),
        "prepared_bytes": len(img_bytes),
        "resized": False,
        "reencoded": False,
    }
    if not TESSERACT_AVAILABLE:
        return img_bytes, metadata

    max_side = resolve_knowledge_image_preprocess_int(
        "raw_ocr_max_side",
        DEFAULT_LOCAL_OCR_MAX_SIDE,
        minimum=640,
        maximum=4096,
    )
    max_bytes = resolve_knowledge_image_preprocess_int(
        "raw_ocr_max_bytes",
        DEFAULT_LOCAL_OCR_MAX_BYTES,
        minimum=256 * 1024,
        maximum=32 * 1024 * 1024,
    )
    metadata["max_side"] = max_side
    metadata["max_bytes"] = max_bytes
    quality_start = resolve_knowledge_image_preprocess_int(
        "raw_ocr_jpeg_quality_start",
        DEFAULT_LOCAL_OCR_JPEG_QUALITY_START,
        minimum=40,
        maximum=95,
    )
    quality_floor = resolve_knowledge_image_preprocess_int(
        "raw_ocr_jpeg_quality_floor",
        DEFAULT_LOCAL_OCR_JPEG_QUALITY_FLOOR,
        minimum=40,
        maximum=quality_start,
    )
    quality_steps = [q for q in (quality_start, 78, quality_floor) if quality_floor <= q <= quality_start]
    qualities = sorted(set(quality_steps), reverse=True)
    metadata["jpeg_quality_start"] = quality_start
    metadata["jpeg_quality_floor"] = quality_floor

    cleaned_bytes, cleanup_info = _strip_png_text_chunks(img_bytes)
    if cleanup_info.get("stripped"):
        img_bytes = cleaned_bytes
        metadata["png_text_chunk_cleanup"] = cleanup_info

    try:
        with Image.open(io.BytesIO(img_bytes)) as image:
            original_format = (image.format or "").lower()
            metadata["original_size"] = [int(image.width), int(image.height)]
            working = image.copy()
    except Exception as exc:
        metadata["skipped_reason"] = f"unreadable_image:{exc}"
        return img_bytes, metadata

    longest = max(working.size)
    if longest > max_side:
        scale = max_side / longest
        next_size = (
            max(1, round(working.width * scale)),
            max(1, round(working.height * scale)),
        )
        working = working.resize(next_size, Image.Resampling.LANCZOS)
        metadata["resized"] = True
        metadata["prepared_size"] = [int(next_size[0]), int(next_size[1])]
    else:
        metadata["prepared_size"] = [int(working.width), int(working.height)]

    if not metadata["resized"] and len(img_bytes) <= max_bytes and original_format in {"jpeg", "jpg"}:
        return img_bytes, metadata

    if working.mode in {"RGBA", "LA"} or (working.mode == "P" and "transparency" in working.info):
        background = Image.new("RGB", working.size, (255, 255, 255))
        alpha = working.convert("RGBA").getchannel("A")
        background.paste(working.convert("RGBA"), mask=alpha)
        working = background
    elif working.mode != "RGB":
        working = working.convert("RGB")

    prepared = img_bytes
    selected_quality = qualities[-1]

    def encode_jpeg(quality: int) -> bytes:
        out = io.BytesIO()
        working.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue()

    for quality in qualities:
        prepared = encode_jpeg(quality)
        selected_quality = quality
        if len(prepared) <= max_bytes:
            break

    metadata["prepared_bytes"] = len(prepared)
    metadata["prepared_size"] = [int(working.width), int(working.height)]
    metadata["jpeg_quality"] = selected_quality
    metadata["reencoded"] = True
    return prepared, metadata


def _vision_model_metadata(method: str, profile_key: str, result: dict | None = None) -> dict:
    diagnostics = (result or {}).get("diagnostics") or {}
    selected_profile = str(diagnostics.get("selected_profile") or profile_key)
    selected_provider = str(diagnostics.get("selected_provider") or "")
    model_degraded = bool(diagnostics.get("fallback_used")) and selected_profile != profile_key
    model_diagnostics = {
        "requested_profile": profile_key,
        "selected_profile": selected_profile,
        "selected_provider": selected_provider,
        "fallback_used": bool(diagnostics.get("fallback_used")),
    }
    if diagnostics.get("image_preprocess"):
        model_diagnostics["image_preprocess"] = diagnostics["image_preprocess"]
    return {
        "method": method,
        "provider": selected_provider,
        "profile_key": profile_key,
        "model_used": selected_profile,
        "model_degraded": model_degraded,
        "model_diagnostics": model_diagnostics,
    }


def classify_raw_collection_status(
    total_rounds: int,
    valid_rounds: int,
    failed_rounds: int,
    task_count: int,
    total_pages: int | None = None,
    valid_pages: int | None = None,
    primary_valid_pages: int | None = None,
) -> str:
    """根据有效内容统计判定 raw 阶段状态。"""
    if total_rounds > 0 and valid_rounds == 0:
        return "failed" if task_count > 0 and failed_rounds >= task_count else "degraded"
    if failed_rounds > 0:
        return "degraded"
    if total_pages is not None and valid_pages is not None:
        if primary_valid_pages is not None:
            if total_pages > 0 and primary_valid_pages == 0:
                return "degraded"
            if total_pages > primary_valid_pages:
                return "degraded"
            return "done"
        if total_pages > 0 and valid_pages == 0:
            return "degraded"
        if total_pages > valid_pages:
            return "degraded"
        return "done"
    if total_rounds > valid_rounds:
        return "degraded"
    return "done"


def completed_raw_pages(rows: list[tuple[int, str]], expected_rounds: int) -> set[int]:
    """Pages with every expected round completed successfully."""
    page_round_count: dict[int, int] = {}
    for page, status in rows:
        if status == "done":
            page_round_count[page] = page_round_count.get(page, 0) + 1
    return {page for page, count in page_round_count.items() if count >= expected_rounds}


def completed_raw_rounds(rows: list[tuple[int, int, str]]) -> set[tuple[int, int]]:
    """Individual (page, round) records that are already durable and reusable."""
    return {
        (int(page), int(round_num))
        for page, round_num, status in rows
        if status == "done"
    }


def summarize_raw_content_quality(
    rows: list[tuple[int, int, str, str, str, int | None, dict | None]],
    *,
    total_pages: int,
    expected_rounds: int,
    visual_document: bool,
) -> dict:
    """Summarize raw rows without treating empty OCR as primary content loss."""
    raw_contents = [content or "" for (_page, _round, _source, content, _status, _duration, _metadata) in rows]
    total_rounds = total_pages * expected_rounds
    valid_rounds = sum(1 for content in raw_contents if content.strip())
    valid_pages = len({
        page
        for (page, _round, _source, content, _status, _duration, _metadata) in rows
        if (content or "").strip()
    })
    primary_source_types = {"text", "vision"} if visual_document else {"text"}
    primary_valid_pages = len({
        page
        for (page, _round, source_type, content, status, _duration, _metadata) in rows
        if source_type in primary_source_types and status == "done" and (content or "").strip()
    })
    optional_empty_rounds = sum(
        1
        for (_page, _round, source_type, content, status, _duration, _metadata) in rows
        if visual_document
        and source_type == "ocr"
        and status != "failed"
        and not (content or "").strip()
    )
    return {
        "total_rounds": total_rounds,
        "valid_rounds": valid_rounds,
        "empty_rounds": max(total_rounds - valid_rounds, 0),
        "valid_pages": valid_pages,
        "empty_pages": max(total_pages - valid_pages, 0),
        "primary_valid_pages": primary_valid_pages,
        "primary_empty_pages": max(total_pages - primary_valid_pages, 0),
        "optional_empty_rounds": optional_empty_rounds,
    }


async def _exec_round_1_text(
    doc_id: int, file_id: int, owner_id: int,
    page: int, caller: str, ext: str = "pdf",
    page_text_map: dict[int, str] | None = None,
    preparse_error: str = "",
) -> dict:
    """第1轮：文本提取。独立 DB 会话，单独 commit。"""
    async with AsyncSessionLocal() as task_db:
        started = perf_counter()
        error_message = ""
        try:
            if preparse_error:
                raise RuntimeError(preparse_error)
            if page_text_map is not None:
                content = page_text_map.get(page, "")
            else:
                parsed = to_legacy_dict(await parse_document(file_id, ext, caller))
                blocks = parsed.get("blocks", [])
                page_texts = [
                    (b.get("text") or "").strip()
                    for b in blocks
                    if (b.get("page") == page or (page == 1 and b.get("page") is None))
                    and (b.get("text") or "").strip()
                ]
                content = "\n\n".join(page_texts)
        except Exception as e:
            logger.warning("Round 1 text extraction failed for doc_id=%d page=%d: %s", doc_id, page, e)
            content = ""
            error_message = str(e)

        duration_ms = round((perf_counter() - started) * 1000)
        status = "done" if content else ("failed" if error_message else "degraded")
        record = KbRawData(
            document_id=doc_id,
            file_id=file_id,
            owner_id=owner_id,
            page=page,
            round=1,
            source_type="text",
            content=content,
            model_used="parser",
            confidence=0.95 if content else 0.0,
            content_hash=_hash_content(content),
            status=status,
            error_message=error_message or None,
            duration_ms=duration_ms,
        )
        task_db.add(record)
        await task_db.commit()
        logger.info("Raw collection round=1 page=%d done (%d chars)", page, len(content))
        return {
            "round": 1,
            "page": page,
            "chars": len(content),
            "status": status,
            "duration_ms": duration_ms,
            "processor": "local_parser",
        }


async def _build_page_text_map(file_id: int, ext: str, caller: str) -> tuple[dict[int, str], str]:
    """Parse the source once and split parser text blocks by page."""
    page_texts: dict[int, list[str]] = {}
    try:
        parsed = to_legacy_dict(await parse_document(file_id, ext, caller))
        for block in parsed.get("blocks", []):
            text = (block.get("text") or "").strip()
            if not text:
                continue
            page = int(block.get("page") or 1)
            page_texts.setdefault(page, []).append(text)
    except Exception as exc:
        return {}, str(exc)
    return {
        page: "\n\n".join(texts)
        for page, texts in page_texts.items()
    }, ""


async def _exec_round_2_ocr(
    doc_id: int, file_id: int, owner_id: int,
    page: int, user_id: int,
    img_bytes: bytes | None = None,
) -> dict:
    """第2轮：截图 OCR。独立 DB 会话，单独 commit。

    优先用 tesseract 出文本+词坐标（方案①：一趟出）。
    若 tesseract 不可用则回退到 VLM OCR（仅文本）。
    """
    from app.services.model_services import describe_image_detailed

    async with AsyncSessionLocal() as task_db:
        started = perf_counter()
        error_message = ""
        profile_key = resolve_knowledge_vision_profile("raw_ocr")
        try:
            if img_bytes is None:
                img_bytes = await render_page_to_image(file_id, page, user_id)
            content = ""
            metadata: dict = _vision_model_metadata("vlm_ocr", profile_key)

            # 方案①：优先 tesseract——一趟出文本+词坐标
            tesseract_result = await _ocr_words_tesseract_async(img_bytes)
            if tesseract_result is not None:
                # 从词坐标组装纯文本
                words = tesseract_result.get("words", [])
                content = " ".join(w["t"] for w in words)
                metadata = {
                    "method": "tesseract_boxes",
                    "provider": "tesseract",
                    "img_w": tesseract_result["img_w"],
                    "img_h": tesseract_result["img_h"],
                    "words": words,
                    "image_preprocess": tesseract_result.get("preprocess") or {},
                }
            else:
                # 回退：纯 VLM OCR（不产生词坐标）
                prompt = await load_prompt(task_db, TRAW_OCR, release_transaction=True)
                async with knowledge_model_call_slot("raw_ocr"):
                    result = await describe_image_detailed(
                        img_bytes,
                        prompt=prompt,
                        mime_type="image/png",
                        profile_key=profile_key,
                    )
                content = str(result.get("content") or "")
                metadata = _vision_model_metadata("vlm_ocr", profile_key, result)
        except Exception as e:
            logger.warning("Round 2 OCR failed for doc_id=%d page=%d: %s", doc_id, page, e)
            content = ""
            metadata = _vision_model_metadata("vlm_ocr", profile_key)
            error_message = str(e)

        duration_ms = round((perf_counter() - started) * 1000)
        status = "done" if content else ("failed" if error_message else "degraded")
        record = KbRawData(
            document_id=doc_id,
            file_id=file_id,
            owner_id=owner_id,
            page=page,
            round=2,
            source_type="ocr",
            content=content,
            model_used="tesseract" if metadata.get("provider") == "tesseract" else str(metadata.get("model_used") or profile_key),
            confidence=0.85 if content else 0.0,
            content_hash=_hash_content(content),
            metadata_json=metadata,
            status=status,
            error_message=error_message or None,
            duration_ms=duration_ms,
        )
        task_db.add(record)
        await task_db.commit()
        logger.info("Raw collection round=2 page=%d done (%d chars, %d words)",
                     page, len(content),
                     len(metadata.get("words", [])))
        return {
            "round": 2,
            "page": page,
            "chars": len(content),
            "status": status,
            "duration_ms": duration_ms,
            "processor": metadata.get("provider") or "vlm",
            "model_degraded": bool(metadata.get("model_degraded")),
            "model_diagnostics": metadata.get("model_diagnostics") or {},
        }


async def _exec_round_3_vision(
    doc_id: int, file_id: int, owner_id: int,
    page: int, user_id: int,
    img_bytes: bytes | None = None,
) -> dict:
    """第3轮：视觉构成。独立 DB 会话，单独 commit。"""
    from app.services.model_services import describe_image_detailed

    async with AsyncSessionLocal() as task_db:
        started = perf_counter()
        error_message = ""
        profile_key = resolve_knowledge_vision_profile("raw_vision")
        metadata = _vision_model_metadata("vlm_vision", profile_key)
        try:
            if img_bytes is None:
                img_bytes = await render_page_to_image(file_id, page, user_id)
            prompt = await load_prompt(task_db, TRAW_VISION, release_transaction=True)
            async with knowledge_model_call_slot("raw_vision"):
                result = await describe_image_detailed(
                    img_bytes,
                    prompt=prompt,
                    mime_type="image/png",
                    profile_key=profile_key,
                )
            content = str(result.get("content") or "")
            metadata = _vision_model_metadata("vlm_vision", profile_key, result)
        except Exception as e:
            logger.warning("Round 3 vision failed for doc_id=%d page=%d: %s", doc_id, page, e)
            content = ""
            error_message = str(e)

        duration_ms = round((perf_counter() - started) * 1000)
        status = "done" if content else ("failed" if error_message else "degraded")
        record = KbRawData(
            document_id=doc_id,
            file_id=file_id,
            owner_id=owner_id,
            page=page,
            round=3,
            source_type="vision",
            content=content,
            model_used=str(metadata.get("model_used") or profile_key),
            confidence=0.80 if content else 0.0,
            content_hash=_hash_content(content),
            metadata_json=metadata,
            status=status,
            error_message=error_message or None,
            duration_ms=duration_ms,
        )
        task_db.add(record)
        await task_db.commit()
        logger.info("Raw collection round=3 page=%d done (%d chars)", page, len(content))
        return {
            "round": 3,
            "page": page,
            "chars": len(content),
            "status": status,
            "duration_ms": duration_ms,
            "processor": metadata.get("provider") or "vlm",
            "model_degraded": bool(metadata.get("model_degraded")),
            "model_diagnostics": metadata.get("model_diagnostics") or {},
        }


async def _pre_render_pages(file_id: int, user_id: int, total_pages: int) -> dict[int, bytes]:
    """预渲染所有 PDF 页面为图片字节（仅一次，round2/round3 共享）。"""
    images: dict[int, bytes] = {}
    for page in range(1, total_pages + 1):
        try:
            images[page] = await render_page_to_image(file_id, page, user_id)
        except Exception as e:
            logger.warning("Pre-render page=%d failed: %s", page, e)
    return images


async def collect_raw_data(db: AsyncSession, doc_id: int, owner_id: int, file_id: int, user_id: int) -> dict:
    """对文档所有页执行三轮并行采集，落盘 kb_raw_data。

    使用 5 并发门池摊平所有 (page, round) 任务，
    每任务独立 DB 会话 + 独立 commit，
    进度三行各自按真实速度前进。

    返回: {"document_id": int, "total_pages": int, "rounds": [...每个任务的结果...], "status": "done"}
    """
    caller = f"user:{user_id}"
    stage_started = perf_counter()

    # 确定页数
    df = await db.execute(select(KbDocument).where(KbDocument.id == doc_id))
    doc = df.scalar_one_or_none()
    if not doc:
        raise ValueError(f"Document {doc_id} not found")

    ext = (doc.extension or "").lower()
    is_pdf = ext == "pdf"
    is_image = ext in IMAGE_FORMATS

    if is_pdf:
        try:
            total_pages = await get_pdf_page_count(file_id, user_id)
        except Exception:
            total_pages = doc.total_pages or 1
    else:
        total_pages = doc.total_pages or 1

    # 更新文档状态
    doc.raw_status = "collecting"
    doc.total_pages = total_pages
    await db.commit()

    # 按文件类型决定采集轮次
    if is_pdf:
        rounds_for_type = [1, 2, 3]
    elif is_image:
        rounds_for_type = [1, 2, 3]
    else:
        rounds_for_type = [1]
    expected_rounds = len(rounds_for_type)

    # 已完成 round 跳过 → 幂等可重入。局部预处理产物必须保留。
    dr = await db.execute(
        select(KbRawData.page, KbRawData.round, KbRawData.status).where(KbRawData.document_id == doc_id)
    )
    done_rounds = completed_raw_rounds(dr.all())
    done_pages = {
        page
        for page in range(1, total_pages + 1)
        if all((page, round_num) in done_rounds for round_num in rounds_for_type)
    }
    await db.commit()

    # 清除未完成 round 的残缺旧记录，但保留其他已完成 round 断点。
    for page in range(1, total_pages + 1):
        for round_num in rounds_for_type:
            if (page, round_num) in done_rounds:
                continue
            async with AsyncSessionLocal() as clean_db:
                await clean_db.execute(
                    sa_delete(KbRawData).where(
                        KbRawData.document_id == doc_id,
                        KbRawData.page == page,
                        KbRawData.round == round_num,
                    )
                )
                await clean_db.commit()

    # 预渲染页面图片（只一次，OCR 与视觉共用）
    page_images: dict[int, bytes] = {}
    page_text_map: dict[int, str] | None = None
    preparse_error = ""
    text_parse_duration_ms = 0
    needs_round_1 = any((page, 1) not in done_rounds for page in range(1, total_pages + 1))
    if 1 in rounds_for_type and needs_round_1:
        text_parse_started = perf_counter()
        page_text_map, preparse_error = await _build_page_text_map(file_id, ext, caller)
        text_parse_duration_ms = round((perf_counter() - text_parse_started) * 1000)
        if preparse_error:
            logger.warning("Pre-parse text map failed for doc_id=%d: %s", doc_id, preparse_error)

    pre_render_started = perf_counter()
    needs_render = any(
        (page, round_num) not in done_rounds
        for page in range(1, total_pages + 1)
        for round_num in (2, 3)
        if round_num in rounds_for_type
    )
    if is_pdf and needs_render:
        page_images = await _pre_render_pages(file_id, user_id, total_pages)
    elif is_image and needs_render:
        # 图片文件：读原始字节一次
        from pathlib import Path

        from app.config import get_settings
        from app.services.file_service import check_file_access as _check_fa
        try:
            async with AsyncSessionLocal() as fdb:
                f_rec = await _check_fa(fdb, file_id, user_id)
            img_path = Path(get_settings().UPLOAD_DIR).resolve() / f_rec.storage_path
            img_bytes = img_path.read_bytes()
            for page in range(1, total_pages + 1):
                page_images[page] = img_bytes
        except Exception as e:
            logger.warning("Cannot read image bytes for file_id=%d: %s", file_id, e)
    pre_render_duration_ms = round((perf_counter() - pre_render_started) * 1000)

    # 并发门池 + 摊平任务列表；配置在下一批 stage 启动时生效。
    raw_collect_concurrency = resolve_knowledge_concurrency("raw_collect", RAW_COLLECT_CONCURRENCY)
    sem = asyncio.Semaphore(raw_collect_concurrency)
    all_results: list[dict] = []

    async def _task_wrapper(round_num: int, page: int) -> dict:
        async with sem:
            if round_num == 1:
                return await _exec_round_1_text(
                    doc_id,
                    file_id,
                    owner_id,
                    page,
                    caller,
                    ext=ext,
                    page_text_map=page_text_map,
                    preparse_error=preparse_error,
                )
            elif round_num == 2:
                return await _exec_round_2_ocr(doc_id, file_id, owner_id, page, user_id, img_bytes=page_images.get(page))
            elif round_num == 3:
                return await _exec_round_3_vision(doc_id, file_id, owner_id, page, user_id, img_bytes=page_images.get(page))
            return {"round": round_num, "page": page, "error": "unknown round"}

    tasks = []
    for page in range(1, total_pages + 1):
        if page in done_pages:
            logger.info("Raw collection page=%d already done, skip", page)
            continue
        for r in rounds_for_type:
            if (page, r) in done_rounds:
                logger.info("Raw collection page=%d round=%d already done, skip", page, r)
                continue
            tasks.append(_task_wrapper(r, page))

    task_wall_started = perf_counter()
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Round task failed: %s", r)
            else:
                all_results.append(r)
    task_wall_duration_ms = round((perf_counter() - task_wall_started) * 1000)

    failed_count = 0
    if tasks:
        failed_count = sum(
            1
            for r in results
            if isinstance(r, Exception) or (isinstance(r, dict) and r.get("error"))
        )

    raw_rows = await db.execute(
        select(
            KbRawData.page,
            KbRawData.round,
            KbRawData.source_type,
            KbRawData.content,
            KbRawData.status,
            KbRawData.duration_ms,
            KbRawData.metadata_json,
        ).where(KbRawData.document_id == doc_id)
    )
    raw_result_rows = raw_rows.all()
    quality = summarize_raw_content_quality(
        raw_result_rows,
        total_pages=total_pages,
        expected_rounds=expected_rounds,
        visual_document=is_pdf or is_image,
    )
    total_rounds = int(quality["total_rounds"])
    valid_rounds = int(quality["valid_rounds"])
    empty_rounds = int(quality["empty_rounds"])
    valid_pages = int(quality["valid_pages"])
    primary_valid_pages = int(quality["primary_valid_pages"])
    primary_empty_pages = int(quality["primary_empty_pages"])
    optional_empty_rounds = int(quality["optional_empty_rounds"])
    failed_row_count = sum(1 for (_page, _round, _source, _content, status, _duration, _metadata) in raw_result_rows if status == "failed")
    failed_pages = sorted({
        page
        for (page, _round, _source, _content, status, _duration, _metadata) in raw_result_rows
        if status == "failed"
    })
    page_durations: dict[int, int] = {}
    round_durations: list[dict] = []
    model_call_duration_ms = 0
    local_processing_duration_ms = 0
    for page, round_num, source_type, content, status, duration, metadata in raw_result_rows:
        duration_value = int(duration or 0)
        page_durations[page] = page_durations.get(page, 0) + duration_value
        metadata = metadata or {}
        provider = str(metadata.get("provider") or "")
        is_model_round = source_type == "vision" or (source_type == "ocr" and provider not in {"", "tesseract"})
        if is_model_round:
            model_call_duration_ms += duration_value
        else:
            local_processing_duration_ms += duration_value
        round_durations.append({
            "page": page,
            "round": round_num,
            "source_type": source_type,
            "status": status,
            "chars": len(content or ""),
            "duration_ms": duration_value,
            "processor": provider or ("local_parser" if source_type == "text" else source_type),
        })

    await db.refresh(doc)
    doc.raw_status = classify_raw_collection_status(
        total_rounds=total_rounds,
        valid_rounds=valid_rounds,
        failed_rounds=failed_count + failed_row_count,
        task_count=len(tasks),
        total_pages=total_pages,
        valid_pages=valid_pages,
        primary_valid_pages=primary_valid_pages,
    )
    if doc.raw_status == "failed":
        logger.error("All raw collection tasks failed for doc_id=%d", doc_id)
    elif doc.raw_status == "degraded":
        logger.warning(
            (
                "Raw collection degraded for doc_id=%d: valid_rounds=%d "
                "empty_rounds=%d primary_empty_pages=%d failed_rounds=%d"
            ),
            doc_id, valid_rounds, empty_rounds, primary_empty_pages, failed_count + failed_row_count,
        )
    await db.commit()

    image_similarity_result = {"status": "skipped", "assets": 0, "pairs": 0, "reason": "no_page_images"}
    if page_images:
        try:
            from .analysis_artifact_service import build_input_hash, build_output_hash, record_analysis_artifact
            from .image_similarity_service import IMAGE_HASH_SCHEMA_VERSION, record_document_image_assets

            image_similarity_result = await record_document_image_assets(
                db,
                owner_id=owner_id,
                document_id=doc_id,
                file_id=file_id,
                page_images=page_images,
                asset_type="image_file" if is_image else "page_render",
            )
            await record_analysis_artifact(
                owner_id=owner_id,
                document_id=doc_id,
                file_id=file_id,
                stage="image_similarity",
                status=str(image_similarity_result.get("status") or "done"),
                unit_type="document",
                unit_key="document",
                input_hash=build_input_hash(
                    stage="image_similarity",
                    document_id=doc_id,
                    file_id=file_id,
                    extra={
                        "pages": sorted(page_images),
                        "hash_schema_version": IMAGE_HASH_SCHEMA_VERSION,
                    },
                ),
                output_hash=build_output_hash(
                    stage="image_similarity",
                    status=str(image_similarity_result.get("status") or "done"),
                    payload=image_similarity_result,
                ),
                preprocess_version=IMAGE_HASH_SCHEMA_VERSION,
                reason="sidecar_image_similarity",
                diagnostics=image_similarity_result,
                metrics={
                    "assets": int(image_similarity_result.get("assets") or 0),
                    "pairs": int(image_similarity_result.get("pairs") or 0),
                    "high": int(image_similarity_result.get("high") or 0),
                    "suspected": int(image_similarity_result.get("suspected") or 0),
                },
            )
        except Exception as e:
            logger.warning("Image similarity sidecar skipped for doc_id=%d: %s", doc_id, e)
            image_similarity_result = {"status": "failed", "assets": 0, "pairs": 0, "error": str(e)}

    model_diagnostics = [
        item.get("model_diagnostics")
        for item in all_results
        if item.get("model_degraded") and item.get("model_diagnostics")
    ]

    return {
        "document_id": doc_id,
        "total_pages": total_pages,
        "total_rounds": total_rounds,
        "valid_rounds": valid_rounds,
        "empty_rounds": empty_rounds,
        "optional_empty_rounds": optional_empty_rounds,
        "valid_pages": valid_pages,
        "empty_pages": max(total_pages - valid_pages, 0),
        "primary_valid_pages": primary_valid_pages,
        "primary_empty_pages": primary_empty_pages,
        "failed_rounds": failed_count + failed_row_count,
        "rounds": all_results,
        "timing": {
            "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
            "text_parse_ms": text_parse_duration_ms,
            "pre_render_ms": pre_render_duration_ms,
            "task_wall_ms": task_wall_duration_ms,
            "raw_collect_concurrency": raw_collect_concurrency,
            "local_processing_ms": local_processing_duration_ms,
            "model_call_ms": model_call_duration_ms,
            "page_durations_ms": dict(sorted(page_durations.items())),
            "round_durations": round_durations,
            "failed_pages": failed_pages,
            "skipped_pages": sorted(done_pages),
            "skipped_rounds": [
                {"page": page, "round": round_num}
                for page, round_num in sorted(done_rounds)
                if page <= total_pages and round_num in rounds_for_type
            ],
        },
        "image_similarity": image_similarity_result,
        "status": doc.raw_status,
        "model_degraded": bool(model_diagnostics),
        "model_diagnostics": model_diagnostics,
    }


async def collect_raw_stage(
    db: AsyncSession,
    doc_id: int,
    owner_id: int,
    file_id: int,
    user_id: int,
    stage: str,
) -> dict:
    """Run one explicit raw node for DAG queue execution."""
    caller = f"user:{user_id}"
    stage_started = perf_counter()
    stage_to_round = {
        "raw_text": 1,
        "raw_ocr": 2,
        "raw_vision": 3,
    }
    round_num = stage_to_round.get(stage)
    if round_num is None:
        return {"document_id": doc_id, "stage": stage, "status": "failed", "error": "unknown_raw_stage"}

    doc = await db.scalar(select(KbDocument).where(KbDocument.id == doc_id))
    if not doc:
        return {"document_id": doc_id, "stage": stage, "status": "skipped", "reason": "doc_missing"}

    ext = (doc.extension or "").lower()
    is_pdf = ext == "pdf"
    is_image = ext in IMAGE_FORMATS
    if round_num in {2, 3} and not (is_pdf or is_image):
        return {
            "document_id": doc_id,
            "stage": stage,
            "round": round_num,
            "status": "skipped",
            "reason": "round_not_required_for_file_type",
        }

    if is_pdf:
        try:
            total_pages = await get_pdf_page_count(file_id, user_id)
        except Exception:
            total_pages = doc.total_pages or 1
    else:
        total_pages = doc.total_pages or 1
    doc.total_pages = total_pages
    if doc.raw_status in {"pending", "", None}:
        doc.raw_status = "collecting"
    await db.commit()

    existing_rows = await db.execute(
        select(KbRawData.page, KbRawData.round, KbRawData.status).where(
            KbRawData.document_id == doc_id,
            KbRawData.round == round_num,
        )
    )
    done_rounds = completed_raw_rounds(existing_rows.all())
    for page in range(1, total_pages + 1):
        if (page, round_num) in done_rounds:
            continue
        async with AsyncSessionLocal() as clean_db:
            await clean_db.execute(
                sa_delete(KbRawData).where(
                    KbRawData.document_id == doc_id,
                    KbRawData.page == page,
                    KbRawData.round == round_num,
                )
            )
            await clean_db.commit()

    page_text_map: dict[int, str] | None = None
    preparse_error = ""
    text_parse_duration_ms = 0
    page_images: dict[int, bytes] = {}
    render_duration_ms = 0

    if round_num == 1 and any((page, 1) not in done_rounds for page in range(1, total_pages + 1)):
        text_parse_started = perf_counter()
        page_text_map, preparse_error = await _build_page_text_map(file_id, ext, caller)
        text_parse_duration_ms = round((perf_counter() - text_parse_started) * 1000)
        if preparse_error:
            logger.warning("Raw stage text map failed for doc_id=%d: %s", doc_id, preparse_error)

    if round_num in {2, 3} and any((page, round_num) not in done_rounds for page in range(1, total_pages + 1)):
        render_started = perf_counter()
        if is_pdf:
            page_images = await _pre_render_pages(file_id, user_id, total_pages)
        elif is_image:
            from pathlib import Path

            from app.config import get_settings
            from app.services.file_service import check_file_access as _check_fa
            try:
                async with AsyncSessionLocal() as fdb:
                    f_rec = await _check_fa(fdb, file_id, user_id)
                img_path = Path(get_settings().UPLOAD_DIR).resolve() / f_rec.storage_path
                img_bytes = img_path.read_bytes()
                page_images = {page: img_bytes for page in range(1, total_pages + 1)}
            except Exception as e:
                logger.warning("Raw stage cannot read image bytes file_id=%d: %s", file_id, e)
        render_duration_ms = round((perf_counter() - render_started) * 1000)

    raw_collect_concurrency = resolve_knowledge_concurrency(
        stage,
        resolve_knowledge_concurrency("raw_collect", RAW_COLLECT_CONCURRENCY),
        maximum=256 if round_num == 1 else 64,
    )
    sem = asyncio.Semaphore(raw_collect_concurrency)
    tasks = []

    async def _task_wrapper(page: int) -> dict:
        async with sem:
            if round_num == 1:
                return await _exec_round_1_text(
                    doc_id,
                    file_id,
                    owner_id,
                    page,
                    caller,
                    ext=ext,
                    page_text_map=page_text_map,
                    preparse_error=preparse_error,
                )
            if round_num == 2:
                return await _exec_round_2_ocr(doc_id, file_id, owner_id, page, user_id, img_bytes=page_images.get(page))
            return await _exec_round_3_vision(doc_id, file_id, owner_id, page, user_id, img_bytes=page_images.get(page))

    for page in range(1, total_pages + 1):
        if (page, round_num) in done_rounds:
            continue
        if round_num in {2, 3} and not page_images.get(page):
            continue
        tasks.append(_task_wrapper(page))

    task_wall_started = perf_counter()
    all_results: list[dict] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for item in results:
            if isinstance(item, Exception):
                logger.warning("Raw stage task failed stage=%s: %s", stage, item)
                all_results.append({"status": "failed", "error": str(item)})
            else:
                all_results.append(item)
    task_wall_duration_ms = round((perf_counter() - task_wall_started) * 1000)

    full_expected_rounds = 3 if (is_pdf or is_image) else 1
    raw_rows = await db.execute(
        select(
            KbRawData.page,
            KbRawData.round,
            KbRawData.source_type,
            KbRawData.content,
            KbRawData.status,
            KbRawData.duration_ms,
            KbRawData.metadata_json,
        ).where(KbRawData.document_id == doc_id)
    )
    raw_result_rows = raw_rows.all()
    quality = summarize_raw_content_quality(
        raw_result_rows,
        total_pages=total_pages,
        expected_rounds=full_expected_rounds,
        visual_document=is_pdf or is_image,
    )
    completed_round_rows = {
        (int(page), int(row_round))
        for page, row_round, _source, _content, status, _duration, _metadata in raw_result_rows
        if status in {"done", "degraded"}
    }
    required_rounds = [1, 2, 3] if (is_pdf or is_image) else [1]
    raw_complete = all(
        (page, required_round) in completed_round_rows
        for page in range(1, total_pages + 1)
        for required_round in required_rounds
    )
    failed_count = sum(1 for item in all_results if item.get("status") == "failed" or item.get("error"))
    await db.refresh(doc)
    if raw_complete:
        doc.raw_status = classify_raw_collection_status(
            total_rounds=int(quality["total_rounds"]),
            valid_rounds=int(quality["valid_rounds"]),
            failed_rounds=failed_count,
            task_count=len(tasks),
            total_pages=total_pages,
            valid_pages=int(quality["valid_pages"]),
            primary_valid_pages=int(quality["primary_valid_pages"]),
        )
    elif failed_count:
        doc.raw_status = "degraded"
    else:
        doc.raw_status = "collecting"
    await db.commit()

    return {
        "document_id": doc_id,
        "stage": stage,
        "round": round_num,
        "status": "done" if not failed_count else "degraded",
        "raw_complete": raw_complete,
        "total_pages": total_pages,
        "rounds": all_results,
        "total_rounds": int(quality["total_rounds"]),
        "valid_rounds": int(quality["valid_rounds"]),
        "empty_rounds": int(quality["empty_rounds"]),
        "valid_pages": int(quality["valid_pages"]),
        "primary_empty_pages": int(quality["primary_empty_pages"]),
        "failed_rounds": failed_count,
        "model_degraded": any(item.get("model_degraded") for item in all_results),
        "model_diagnostics": [
            item.get("model_diagnostics")
            for item in all_results
            if item.get("model_degraded") and item.get("model_diagnostics")
        ],
        "timing": {
            "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
            "text_parse_ms": text_parse_duration_ms,
            "render_ms": render_duration_ms,
            "task_wall_ms": task_wall_duration_ms,
            "raw_stage_concurrency": raw_collect_concurrency,
            "skipped_rounds": [
                {"page": page, "round": existing_round}
                for page, existing_round in sorted(done_rounds)
                if existing_round == round_num
            ],
        },
    }


async def get_raw_data(
    db: AsyncSession, document_id: int, page: int | None = None,
    round_num: int | None = None,
) -> list[dict]:
    """查询原始采集数据。

    返回: [{"id": int, "page": int, "round": int, "source_type": str, "content": str, ...}, ...]
    """
    stmt = select(KbRawData).where(KbRawData.document_id == document_id)
    if page is not None:
        stmt = stmt.where(KbRawData.page == page)
    if round_num is not None:
        stmt = stmt.where(KbRawData.round == round_num)
    stmt = stmt.order_by(KbRawData.page, KbRawData.round)

    r = await db.execute(stmt)
    records = r.scalars().all()
    return [
        {
            "id": rec.id,
            "page": rec.page,
            "round": rec.round,
            "source_type": rec.source_type,
            "content": rec.content,
            "model_used": rec.model_used,
            "confidence": rec.confidence,
            "content_hash": rec.content_hash,
            "status": getattr(rec, "status", "done"),
            "error_message": getattr(rec, "error_message", None),
            "duration_ms": getattr(rec, "duration_ms", None),
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        }
        for rec in records
    ]


async def get_ocr_words(
    db: AsyncSession, file_id: int, page: int, owner_id: int,
) -> dict:
    """获取指定文件某页的 OCR 词坐标（供 pdf-viewer 跨模块调用）。

    从 round-2 原始采集记录的 metadata_json 读 words + img_w/img_h。
    若该文件尚未被知识库采集 / 该页不是 tesseract OCR → 返回空。
    """
    # 先查文档
    dr = await db.execute(
        select(KbDocument).where(
            KbDocument.file_id == file_id,
            KbDocument.owner_id == owner_id,
            KbDocument.deleted.is_(False),
        )
    )
    doc = dr.scalar_one_or_none()
    if not doc:
        return {"words": [], "img_w": 0, "img_h": 0}

    rr = await db.execute(
        select(KbRawData).where(
            KbRawData.document_id == doc.id,
            KbRawData.page == page,
            KbRawData.round == 2,
        ).order_by(KbRawData.id.desc()).limit(1)
    )
    rec = rr.scalar_one_or_none()
    if not rec or not rec.metadata_json:
        return {"words": [], "img_w": 0, "img_h": 0}

    meta = rec.metadata_json
    words = meta.get("words", [])
    return {
        "words": words,
        "img_w": meta.get("img_w", 0),
        "img_h": meta.get("img_h", 0),
    }
