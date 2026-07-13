from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.models.file import File
from app.services import image_derivative_service
from PIL import Image


def _patch_upload_root(monkeypatch, tmp_path: Path) -> Path:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(
        image_derivative_service,
        "get_settings",
        lambda: SimpleNamespace(UPLOAD_DIR=str(upload_root)),
    )
    return upload_root


def test_build_standard_image_derivative_normalizes_web_image(monkeypatch, tmp_path: Path) -> None:
    upload_root = _patch_upload_root(monkeypatch, tmp_path)
    source_path = upload_root / "aa" / "bb" / "source.webp"
    source_path.parent.mkdir(parents=True)
    Image.new("RGBA", (80, 40), (255, 0, 0, 128)).save(source_path, format="WEBP")
    source_bytes = source_path.read_bytes()

    file = File(
        id=77,
        name="wechat-drag",
        extension="webp",
        size=len(source_bytes),
        storage_path="aa/bb/source.webp",
        mime_type="image/webp",
        md5_hash="0" * 32,
        owner_id=1,
    )

    derivative = image_derivative_service._build_standard_image_derivative(file, source_path)

    assert derivative.kind == image_derivative_service.STANDARD_IMAGE_KIND
    assert derivative.mime_type == "image/jpeg"
    assert derivative.storage_path.startswith("derivatives/77/")
    assert derivative.width == 80
    assert derivative.height == 40
    output_path = upload_root / derivative.storage_path
    assert output_path.is_file()
    with Image.open(output_path) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.mode == "RGB"


def test_jfif_upload_variant_is_standardizable(monkeypatch, tmp_path: Path) -> None:
    upload_root = _patch_upload_root(monkeypatch, tmp_path)
    source_path = upload_root / "cc" / "dd" / "source.jfif"
    source_path.parent.mkdir(parents=True)
    Image.new("RGB", (64, 48), (20, 120, 210)).save(source_path, format="JPEG")
    source_bytes = source_path.read_bytes()

    file = File(
        id=78,
        name="wechat-jpeg",
        extension="jfif",
        size=len(source_bytes),
        storage_path="cc/dd/source.jfif",
        mime_type="image/jpeg",
        md5_hash="1" * 32,
        owner_id=1,
    )

    assert image_derivative_service.is_standardizable_image(file) is True
    derivative = image_derivative_service._build_standard_image_derivative(file, source_path)

    output_path = upload_root / derivative.storage_path
    with Image.open(output_path) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.size == (64, 48)


def test_svg_is_not_standardizable() -> None:
    file = File(
        id=88,
        name="vector",
        extension="svg",
        size=12,
        storage_path="vector.svg",
        mime_type="image/svg+xml",
        owner_id=1,
    )

    assert image_derivative_service.is_standardizable_image(file) is False
