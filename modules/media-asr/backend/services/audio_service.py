import asyncio
import shutil
from pathlib import Path
from typing import Optional

from app.core.exceptions import ValidationError

SUPPORTED_AUDIO_OUTPUT_FORMATS = {"wav", "mp3", "m4a", "flac", "ogg"}


def validate_sample_rate(sample_rate: int) -> int:
    if sample_rate not in {8000, 16000, 22050, 24000, 32000, 44100, 48000}:
        raise ValidationError("sample_rate must be one of 8000, 16000, 22050, 24000, 32000, 44100, 48000")
    return sample_rate


def validate_audio_format(audio_format: str) -> str:
    normalized = audio_format.lower().lstrip(".")
    if normalized not in SUPPORTED_AUDIO_OUTPUT_FORMATS:
        raise ValidationError(
            f"audio_format must be one of {', '.join(sorted(SUPPORTED_AUDIO_OUTPUT_FORMATS))}"
        )
    return normalized


def copy_temp_file(source_path: Path, target_dir: Path, filename: str) -> Path:
    target_path = target_dir / filename
    shutil.copy2(source_path, target_path)
    return target_path


async def extract_audio_from_video(
    source_path: Path,
    output_dir: Path,
    sample_rate: int = 16000,
    audio_format: str = "wav",
) -> dict:
    codec_map = {"wav": "pcm_s16le", "mp3": "libmp3lame", "m4a": "aac", "flac": "flac", "ogg": "libvorbis"}
    audio_codec = codec_map.get(audio_format, "pcm_s16le")

    output_path = output_dir / f"audio.{audio_format}"

    args = [
        "ffmpeg", "-y",
        "-i", str(source_path),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-acodec", audio_codec,
        str(output_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"ffmpeg timed out after 600s extracting audio from {source_path.name}")

    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")[-2000:] if stderr else "unknown error"
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}): {error_msg}")

    size = output_path.stat().st_size
    duration = await _get_duration(output_path)

    return {
        "audio_path": output_path,
        "duration_seconds": duration,
        "size": size,
    }


async def transcribe_audio_file(
    audio_path: Path,
    model: str = "large-v3",
    language: Optional[str] = None,
) -> dict:
    try:
        import mlx_whisper
    except ImportError:
        raise RuntimeError(
            "mlx_whisper is not installed. Install it with: pip install mlx-whisper"
        )

    _MODEL_MAP = {
        "tiny": "mlx-community/whisper-tiny",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v2": "mlx-community/whisper-large-v2",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "turbo": "mlx-community/whisper-large-v3-turbo",
    }
    hf_model = _MODEL_MAP.get(model, model)

    kwargs: dict = {"verbose": False}
    kwargs["path_or_hf_repo"] = hf_model
    if language is not None:
        kwargs["language"] = language

    import os as _os
    old_no_proxy = _os.environ.pop("no_proxy", None)
    old_NO_PROXY = _os.environ.pop("NO_PROXY", None)
    try:
        result = mlx_whisper.transcribe(str(audio_path), **kwargs)
    except TypeError as e:
        if "unexpected keyword argument" in str(e).lower() and "language" in str(e):
            kwargs.pop("language", None)
            result = mlx_whisper.transcribe(str(audio_path), **kwargs)
        else:
            raise
    finally:
        if old_no_proxy is not None:
            _os.environ["no_proxy"] = old_no_proxy
        if old_NO_PROXY is not None:
            _os.environ["NO_PROXY"] = old_NO_PROXY

    if not isinstance(result, dict):
        raise RuntimeError(f"mlx_whisper returned unexpected type: {type(result)}")

    text = result.get("text", "")
    segments_raw = result.get("segments", [])

    segments = []
    for seg in segments_raw:
        segments.append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": seg.get("text", ""),
        })

    return {
        "text": text,
        "segments": segments,
    }


async def _get_duration(file_path: Path) -> Optional[float]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return float(stdout.decode().strip())
    except Exception:
        pass
    return None


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}:{secs:05.2f}"
    return f"{secs:04.1f}"


def build_segment_blocks(segments: list[dict]) -> list[dict]:
    blocks = []
    for seg in segments:
        start_str = format_timestamp(seg["start"])
        end_str = format_timestamp(seg["end"])
        block_text = f"[{start_str} - {end_str}] {seg['text']}"
        blocks.append({
            "type": "paragraph",
            "text": block_text,
            "page": None,
            "resource_ref": None,
        })
    return blocks
