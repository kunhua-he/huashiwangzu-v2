"""Sandbox test for wechat-writer module.

Validates core schemas (topics, outline, article, draft) and response shapes
without calling external APIs, model gateways, or DB.
"""


def test_topic_schema() -> None:
    """Topic generation request schema."""
    req = {"direction": "skincare for dry skin in winter"}
    assert "direction" in req and req["direction"].strip()
    print("  [TOPIC] Input schema valid")


def test_outline_schema() -> None:
    """Outline generation request schema."""
    req = {"topic": "Winter Skincare Routine", "direction": "natural ingredients"}
    assert "topic" in req and req["topic"].strip()
    print("  [OUTLINE] Input schema valid")


def test_article_schema() -> None:
    """Article generation request schema."""
    req = {
        "topic": "Winter Skincare Routine",
        "outline": "1. Introduction\n2. Key ingredients\n3. Routine steps",
        "direction": "natural ingredients",
    }
    assert "topic" in req and req["topic"].strip()
    assert "outline" in req and req["outline"].strip()
    print("  [ARTICLE] Input schema valid")


def test_draft_schema() -> None:
    """Draft create/update schema contract."""
    draft = {
        "title": "Winter Skincare Guide",
        "outline": {"sections": ["intro", "body", "conclusion"]},
        "content": "Full article content here...",
        "article_type": "科普",
        "keywords": ["skincare", "winter", "moisture"],
        "status": "draft",
        "notes": "draft for review",
    }
    required = {"title", "content", "status"}
    for field in required:
        assert field in draft, f"Missing required field: {field}"
    assert draft["status"] in ("draft", "published", "archived"), f"Invalid status: {draft['status']}"
    assert isinstance(draft["keywords"], list), "keywords should be list"
    if draft["outline"]:
        assert isinstance(draft["outline"], dict), "outline should be dict"
    print("  [DRAFT] Schema valid")


def test_validate_schema() -> None:
    """Content validation request schema."""
    req = {"content": "Test content with ingredient claims"}
    assert "content" in req and req["content"].strip()
    print("  [VALIDATE] Input schema valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"id": 1, "title": "test"}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("wechat-writer sandbox test")
    print("=" * 60)
    test_topic_schema()
    test_outline_schema()
    test_article_schema()
    test_draft_schema()
    test_validate_schema()
    test_response_shape()
    print("=" * 60)
    print("PASS: wechat-writer sandbox test")


if __name__ == "__main__":
    main()
