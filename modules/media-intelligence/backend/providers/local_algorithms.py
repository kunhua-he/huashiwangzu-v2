from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import MediaContext, MediaProvider, StageResult


class LocalAlgorithmProvider(MediaProvider):
    provider_key = "local_algorithms.local_facts"

    async def run(self, context: MediaContext) -> StageResult:
        action = str(context.options.get("action", "analyze"))
        degraded: list[dict[str, str]] = []
        metadata = _metadata(context, degraded)
        data: dict[str, Any] = {"metadata": metadata}

        if action in {"analyze_image", "analyze_video", "extract_keyframes"} and context.media_type == "video":
            keyframes = _timeline_keyframes(context, metadata)
            data["keyframes"] = keyframes
            if not keyframes:
                degraded.append(_degraded(
                    code="keyframes_unavailable",
                    dependency="ffprobe",
                    message="Video duration is unavailable, so timeline keyframe markers could not be derived.",
                    install_command="brew install ffmpeg",
                ))
        if action in {"analyze_image", "analyze_video", "ocr"}:
            data["ocr"] = _ocr_result(context, degraded)
        if action in {"analyze_image", "analyze_video", "detect_objects"}:
            data["objects"] = _object_result(context, degraded)
        if action in {"analyze_image", "embed_image"} and context.media_type == "image":
            embedding = _image_fingerprint(context, degraded)
            if embedding is not None:
                data["embedding"] = embedding

        if degraded:
            data["degraded"] = degraded
        return StageResult(
            stage="local_algorithms",
            provider=self.provider_key,
            status="degraded" if degraded else "ok",
            data=data,
            warnings=[item["message"] for item in degraded],
            confidence=0.72 if not degraded else 0.55,
        )


def _metadata(context: MediaContext, degraded: list[dict[str, str]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "file_id": context.file_id,
        "file_name": context.file_name,
        "extension": context.extension,
        "media_type": context.media_type,
        "size_bytes": context.size_bytes,
        "head_sha256": context.head_sha256,
    }
    if context.media_type == "image":
        metadata.update(_image_metadata(context.path, degraded))
    else:
        metadata.update(_video_metadata(context.path, degraded))
    return metadata


def _image_metadata(path: Path, degraded: list[dict[str, str]]) -> dict[str, Any]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        degraded.append(_degraded(
            code="pillow_missing",
            dependency="Pillow",
            message="Pillow is not installed; image dimensions and format metadata are unavailable.",
            install_command="backend/.venv/bin/python -m pip install Pillow",
        ))
        return {}

    try:
        with Image.open(path) as image:
            image.load()
            metadata: dict[str, Any] = {
                "width": int(image.width),
                "height": int(image.height),
                "format": str(image.format or "").lower() or None,
                "mode": image.mode,
                "frame_count": getattr(image, "n_frames", 1),
                "is_animated": bool(getattr(image, "is_animated", False)),
            }
            dpi = image.info.get("dpi")
            if isinstance(dpi, tuple) and len(dpi) >= 2:
                metadata["dpi"] = [float(dpi[0]), float(dpi[1])]
            return metadata
    except (OSError, UnidentifiedImageError) as exc:
        degraded.append(_degraded(
            code="image_metadata_failed",
            dependency="Pillow",
            message=f"Pillow could not read image metadata: {exc}",
            install_command="Verify the file is a supported image or install Pillow codec extras.",
        ))
        return {}


def _video_metadata(path: Path, degraded: list[dict[str, str]]) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        degraded.append(_degraded(
            code="ffprobe_missing",
            dependency="ffprobe",
            message="ffprobe is not installed; video duration, dimensions, frame rate, and codec are unavailable.",
            install_command="brew install ffmpeg",
        ))
        return {}

    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        degraded.append(_degraded(
            code="ffprobe_failed",
            dependency="ffprobe",
            message=f"ffprobe execution failed: {exc}",
            install_command="brew install ffmpeg",
        ))
        return {}
    if completed.returncode != 0:
        message = completed.stderr.strip() or "ffprobe returned a non-zero exit code."
        degraded.append(_degraded(
            code="ffprobe_unreadable",
            dependency="ffprobe",
            message=message,
            install_command="Verify the file is a supported video and ffmpeg is installed.",
        ))
        return {}

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        degraded.append(_degraded(
            code="ffprobe_invalid_json",
            dependency="ffprobe",
            message=f"ffprobe returned invalid JSON: {exc}",
            install_command="brew install ffmpeg",
        ))
        return {}
    return _parse_ffprobe(payload)


def _parse_ffprobe(payload: dict[str, Any]) -> dict[str, Any]:
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    format_info = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    duration = _float_or_none(video_stream.get("duration")) or _float_or_none(format_info.get("duration"))
    metadata: dict[str, Any] = {
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "bit_rate": _int_or_none(format_info.get("bit_rate")),
        "format_name": format_info.get("format_name"),
        "video_codec": video_stream.get("codec_name"),
        "width": _int_or_none(video_stream.get("width")),
        "height": _int_or_none(video_stream.get("height")),
        "frame_rate": _parse_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "frame_count": _int_or_none(video_stream.get("nb_frames")),
        "audio_stream_count": len(audio_streams),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _timeline_keyframes(context: MediaContext, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    duration = _float_or_none(metadata.get("duration_seconds"))
    if duration is None or duration <= 0:
        return []
    max_keyframes = _bounded_int(context.options.get("max_keyframes"), 5, 1, 12)
    count = max(1, min(max_keyframes, math.ceil(duration / 30)))
    if count == 1:
        timestamps = [min(duration / 2, duration)]
    else:
        step = duration / (count + 1)
        timestamps = [step * (idx + 1) for idx in range(count)]
    return [
        {
            "index": idx,
            "timestamp_seconds": round(timestamp, 3),
            "source": "ffprobe_timeline",
            "artifact_path": None,
        }
        for idx, timestamp in enumerate(timestamps)
    ]


def _ocr_result(context: MediaContext, degraded: list[dict[str, str]]) -> dict[str, Any]:
    degraded.append(_degraded(
        code="ocr_engine_missing",
        dependency="ocr_engine",
        message="No OCR engine is configured; text extraction is unavailable for this local pass.",
        install_command="Install and wire PaddleOCR or Tesseract in the media-intelligence local layer.",
    ))
    return {
        "engine": "not_configured",
        "text": "",
        "regions": [],
        "language": None,
        "status": "degraded",
        "media_type": context.media_type,
    }


def _object_result(context: MediaContext, degraded: list[dict[str, str]]) -> list[dict[str, Any]]:
    degraded.append(_degraded(
        code="object_detector_missing",
        dependency="object_detector",
        message="No object detector is configured; object boxes are unavailable for this local pass.",
        install_command="Install and wire OpenCV/YOLO or another detector in the media-intelligence local layer.",
    ))
    return []


def _image_fingerprint(context: MediaContext, degraded: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        degraded.append(_degraded(
            code="pillow_missing_for_fingerprint",
            dependency="Pillow",
            message="Pillow is not installed; image perceptual fingerprint is unavailable.",
            install_command="backend/.venv/bin/python -m pip install Pillow",
        ))
        return None

    try:
        with Image.open(context.path) as image:
            dimensions = _bounded_int(context.options.get("dimensions"), 64, 8, 1024)
            side = math.ceil(math.sqrt(dimensions))
            grayscale = image.convert("L").resize((side, side))
            if hasattr(grayscale, "get_flattened_data"):
                pixels = list(grayscale.get_flattened_data())[:dimensions]
            else:
                pixels = list(grayscale.getdata())[:dimensions]
    except (OSError, UnidentifiedImageError) as exc:
        degraded.append(_degraded(
            code="image_fingerprint_failed",
            dependency="Pillow",
            message=f"Pillow could not build an image fingerprint: {exc}",
            install_command="Verify the file is a supported image or install Pillow codec extras.",
        ))
        return None

    average = sum(pixels) / len(pixels)
    bits = [1 if pixel >= average else 0 for pixel in pixels]
    return {
        "algorithm": "average_intensity_hash",
        "hash": _bits_to_hex(bits),
        "dimensions": len(bits),
        "vector": bits,
        "purpose": "local_dedupe",
    }


def _bits_to_hex(bits: list[int]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return f"{value:0{math.ceil(len(bits) / 4)}x}"


def _parse_rate(value: object) -> float | None:
    if not isinstance(value, str) or value in {"", "0/0"}:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        top = _float_or_none(numerator)
        bottom = _float_or_none(denominator)
        if top is None or bottom in {None, 0.0}:
            return None
        return round(top / bottom, 3)
    parsed = _float_or_none(value)
    return round(parsed, 3) if parsed is not None else None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _degraded(code: str, dependency: str, message: str, install_command: str) -> dict[str, str]:
    return {
        "code": code,
        "dependency": dependency,
        "message": message,
        "install_command": install_command,
    }
