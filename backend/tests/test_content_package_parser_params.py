"""Tests for content package parser orchestration parameters."""
import os

os.environ.setdefault("JWT_SECRET", "test-secret-for-content-package-parser-params")

from app.services.content.package_service import _build_parser_params


def test_content_package_image_parser_uses_local_analysis_mode() -> None:
    params = _build_parser_params(123, "JPG", "image-vision", "describe")

    assert params == {"file_id": 123, "analysis_mode": "local"}


def test_content_package_non_image_parser_keeps_minimal_params() -> None:
    params = _build_parser_params(456, "pdf", "pdf-parser", "parse")

    assert params == {"file_id": 456}
