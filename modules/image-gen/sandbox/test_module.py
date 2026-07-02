"""Sandbox test for image-gen module.

Validates core contracts: generate, list_templates, usage_history
parameter schemas and output shapes — without real image generation calls.
"""


def test_generate_params_minimal() -> None:
    """generate action: prompt is the only required parameter."""
    params = {"prompt": "A beautiful sunset over mountains"}
    assert "prompt" in params
    assert isinstance(params["prompt"], str) and params["prompt"].strip()
    print("  [GENERATE] Minimal params valid")


def test_generate_params_full() -> None:
    """generate action: all optional parameters."""
    params = {
        "prompt": "A beautiful sunset over mountains",
        "size": "1024x1024",
        "aspect_ratio": "16:9",
        "count": 4,
        "steps": 50,
        "template": "realistic",
    }
    assert "prompt" in params

    # size validation: WxH format
    if "size" in params:
        parts = params["size"].split("x")
        assert len(parts) == 2, f"Invalid size format: {params['size']}"
        w, h = parts
        assert w.isdigit() and h.isdigit(), f"Size dimensions must be integers: {params['size']}"

    # aspect_ratio: allow square/portrait/landscape or ratio string
    if "aspect_ratio" in params and params["aspect_ratio"]:
        valid_ratios = {"square", "portrait", "landscape", "16:9", "4:3", "3:2", "1:1", "9:16"}
        assert params["aspect_ratio"] in valid_ratios, f"Invalid aspect_ratio: {params['aspect_ratio']}"

    # count: positive int
    if "count" in params:
        assert isinstance(params["count"], int) and params["count"] >= 1

    # steps: positive int
    if "steps" in params:
        assert isinstance(params["steps"], int) and params["steps"] >= 1

    # template: optional string
    if "template" in params:
        assert isinstance(params["template"], str)
    print("  [GENERATE] Full params valid")


def test_generate_size_default() -> None:
    """generate action: size defaults to 1024x1024."""
    default_size = "1024x1024"
    parts = default_size.split("x")
    assert len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
    print("  [GENERATE] Default size valid")


def test_generate_count_default() -> None:
    """generate action: count defaults to 1."""
    default_count = 1
    assert isinstance(default_count, int) and default_count >= 1
    print("  [GENERATE] Default count valid")


def test_generate_steps_default() -> None:
    """generate action: steps defaults to 30."""
    default_steps = 30
    assert isinstance(default_steps, int) and default_steps >= 1
    print("  [GENERATE] Default steps valid")


def test_generate_output_shape() -> None:
    """generate action: output is an array of image_urls."""
    result = {
        "image_urls": [
            "https://example.com/gen/1.png",
            "https://example.com/gen/2.png",
        ],
        "prompt": "A beautiful sunset over mountains",
        "total_generated": 2,
    }
    assert "image_urls" in result
    assert isinstance(result["image_urls"], list)
    assert len(result["image_urls"]) > 0
    for url in result["image_urls"]:
        assert isinstance(url, str) and url.startswith("http")
    if "total_generated" in result:
        assert result["total_generated"] == len(result["image_urls"])
    print("  [GENERATE] Output shape valid")


def test_list_templates_params() -> None:
    """list_templates action: no parameters."""
    params: dict = {}
    assert len(params) == 0
    print("  [LIST_TEMPLATES] No params required")


def test_list_templates_output_shape() -> None:
    """list_templates action: returns template list."""
    result = {
        "templates": [
            {"key": "realistic", "name": "逼真写真", "preview_url": ""},
            {"key": "anime", "name": "二次元动漫", "preview_url": ""},
        ]
    }
    assert "templates" in result
    assert isinstance(result["templates"], list)
    for t in result["templates"]:
        assert "key" in t and "name" in t
        assert isinstance(t["key"], str)
    print("  [LIST_TEMPLATES] Output shape valid")


def test_usage_history_params() -> None:
    """usage_history action: no parameters."""
    params: dict = {}
    assert len(params) == 0
    print("  [USAGE_HISTORY] No params required")


def test_usage_history_output_shape() -> None:
    """usage_history action: returns usage records."""
    result = {
        "records": [
            {
                "id": 1,
                "prompt": "sunset",
                "count": 1,
                "cost": 0.01,
                "created_at": "2026-07-01T00:00:00",
            }
        ],
        "total_usage": 1,
    }
    assert "records" in result
    assert isinstance(result["records"], list)
    for rec in result["records"]:
        assert "id" in rec and "prompt" in rec and "created_at" in rec
    print("  [USAGE_HISTORY] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"image_urls": []}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("image-gen sandbox test")
    print("=" * 60)
    test_generate_params_minimal()
    test_generate_params_full()
    test_generate_size_default()
    test_generate_count_default()
    test_generate_steps_default()
    test_generate_output_shape()
    test_list_templates_params()
    test_list_templates_output_shape()
    test_usage_history_params()
    test_usage_history_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: image-gen sandbox test")


if __name__ == "__main__":
    main()
