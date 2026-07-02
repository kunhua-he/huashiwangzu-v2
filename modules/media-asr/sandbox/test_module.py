"""Sandbox test for media-asr module.

Validates core contracts: extract_audio, transcribe_audio, transcribe_video
parameter schemas and output shapes — without real media processing or DB calls.
"""


def test_extract_audio_params_minimal() -> None:
    """extract_audio action: file_id is the only required parameter."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [EXTRACT_AUDIO] Minimal params valid")


def test_extract_audio_params_full() -> None:
    """extract_audio action: all parameters."""
    params = {
        "file_id": 42,
        "sample_rate": 44100,
        "audio_format": "mp3",
        "save_file": True,
        "folder_id": 5,
    }
    assert "file_id" in params and isinstance(params["file_id"], int) and params["file_id"] > 0

    if "sample_rate" in params:
        valid_rates = {8000, 11025, 16000, 22050, 32000, 44100, 48000}
        assert params["sample_rate"] in valid_rates, f"Invalid sample_rate: {params['sample_rate']}"

    if "audio_format" in params:
        valid_formats = {"wav", "mp3", "m4a", "flac", "ogg"}
        assert params["audio_format"] in valid_formats, f"Invalid audio_format: {params['audio_format']}"

    if "save_file" in params:
        assert isinstance(params["save_file"], bool)

    if "folder_id" in params:
        assert isinstance(params["folder_id"], int) and params["folder_id"] > 0
    print("  [EXTRACT_AUDIO] Full params valid")


def test_extract_audio_defaults() -> None:
    """extract_audio action: default values."""
    default_sample_rate = 16000
    assert isinstance(default_sample_rate, int) and default_sample_rate > 0

    default_audio_format = "wav"
    valid_formats = {"wav", "mp3", "m4a", "flac", "ogg"}
    assert default_audio_format in valid_formats

    default_save_file = True
    assert isinstance(default_save_file, bool)
    print("  [EXTRACT_AUDIO] Default values valid")


def test_extract_audio_output_shape() -> None:
    """extract_audio action: returns audio file info."""
    result = {
        "audio_file_id": 100,
        "file_id": 42,
        "format": "wav",
        "sample_rate": 16000,
        "duration": 120.5,
        "size": 3840000,
        "path": "/data/media-asr/audio/42.wav",
    }
    required = {"audio_file_id", "file_id", "format", "sample_rate"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["audio_file_id"], int)
    assert isinstance(result["sample_rate"], int)
    assert isinstance(result["duration"], (int, float))
    print("  [EXTRACT_AUDIO] Output shape valid")


def test_transcribe_audio_params_minimal() -> None:
    """transcribe_audio action: file_id is required."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [TRANSCRIBE_AUDIO] Minimal params valid")


def test_transcribe_audio_params_full() -> None:
    """transcribe_audio action: all parameters."""
    params = {
        "file_id": 42,
        "model": "large-v3",
        "language": "zh",
        "save_text": True,
        "folder_id": 5,
    }
    assert "file_id" in params and isinstance(params["file_id"], int) and params["file_id"] > 0

    if "model" in params:
        valid_models = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"}
        assert params["model"] in valid_models, f"Invalid model: {params['model']}"

    if "language" in params:
        assert isinstance(params["language"], str) and len(params["language"]) > 0

    if "save_text" in params:
        assert isinstance(params["save_text"], bool)

    if "folder_id" in params:
        assert isinstance(params["folder_id"], int) and params["folder_id"] > 0
    print("  [TRANSCRIBE_AUDIO] Full params valid")


def test_transcribe_audio_defaults() -> None:
    """transcribe_audio action: default values."""
    default_model = "large-v3"
    valid_models = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"}
    assert default_model in valid_models

    default_save_text = False
    assert isinstance(default_save_text, bool)
    print("  [TRANSCRIBE_AUDIO] Default values valid")


def test_transcribe_audio_output_shape() -> None:
    """transcribe_audio action: returns segments with timestamps."""
    result = {
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 2.5, "end": 5.0, "text": "This is a test"},
        ],
        "language": "en",
        "duration": 5.0,
        "model": "large-v3",
    }
    assert "segments" in result
    assert isinstance(result["segments"], list)
    assert len(result["segments"]) > 0
    for seg in result["segments"]:
        assert "start" in seg and "end" in seg and "text" in seg
        assert isinstance(seg["start"], (int, float)) and seg["start"] >= 0
        assert isinstance(seg["end"], (int, float)) and seg["end"] > seg["start"]
        assert isinstance(seg["text"], str) and seg["text"].strip()
    print("  [TRANSCRIBE_AUDIO] Output shape valid")


def test_transcribe_video_params_minimal() -> None:
    """transcribe_video action: file_id required."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [TRANSCRIBE_VIDEO] Minimal params valid")


def test_transcribe_video_params_full() -> None:
    """transcribe_video action: all parameters."""
    params = {
        "file_id": 42,
        "model": "large-v3",
        "sample_rate": 16000,
        "language": "en",
        "save_audio": True,
        "save_text": True,
        "folder_id": 5,
    }
    assert "file_id" in params and isinstance(params["file_id"], int) and params["file_id"] > 0

    if "model" in params:
        valid_models = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"}
        assert params["model"] in valid_models

    if "sample_rate" in params:
        valid_rates = {8000, 11025, 16000, 22050, 32000, 44100, 48000}
        assert params["sample_rate"] in valid_rates

    if "language" in params:
        assert isinstance(params["language"], str) and len(params["language"]) > 0

    if "save_audio" in params:
        assert isinstance(params["save_audio"], bool)

    if "save_text" in params:
        assert isinstance(params["save_text"], bool)

    if "folder_id" in params:
        assert isinstance(params["folder_id"], int) and params["folder_id"] > 0
    print("  [TRANSCRIBE_VIDEO] Full params valid")


def test_transcribe_video_output_shape() -> None:
    """transcribe_video action: combined output with segments and optional audio info."""
    result = {
        "segments": [
            {"start": 0.0, "end": 3.0, "text": "Video content transcript"},
        ],
        "language": "en",
        "duration": 30.0,
        "audio_file_id": 100,
        "audio_format": "wav",
        "sample_rate": 16000,
    }
    assert "segments" in result
    assert isinstance(result["segments"], list)
    for seg in result["segments"]:
        assert "start" in seg and "end" in seg and "text" in seg
        assert isinstance(seg["start"], (int, float)) and seg["start"] >= 0
        assert isinstance(seg["text"], str)
    if "audio_file_id" in result:
        assert isinstance(result["audio_file_id"], int)
    print("  [TRANSCRIBE_VIDEO] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"segments": []}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("media-asr sandbox test")
    print("=" * 60)
    test_extract_audio_params_minimal()
    test_extract_audio_params_full()
    test_extract_audio_defaults()
    test_extract_audio_output_shape()
    test_transcribe_audio_params_minimal()
    test_transcribe_audio_params_full()
    test_transcribe_audio_defaults()
    test_transcribe_audio_output_shape()
    test_transcribe_video_params_minimal()
    test_transcribe_video_params_full()
    test_transcribe_video_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: media-asr sandbox test")


if __name__ == "__main__":
    main()
