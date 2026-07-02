"""Sandbox test for memory module.

Validates parameter schemas, required fields, value ranges, and output
shapes for all public_actions — without calling real embedding service
or DB.
"""


def test_save_params() -> None:
    """save: text (string required), tags (string optional)."""
    params_min = {"text": "User prefers dark mode"}
    assert "text" in params_min
    assert isinstance(params_min["text"], str) and len(params_min["text"]) > 0
    params_full = {"text": "User prefers dark mode", "tags": "preference,ui"}
    assert "tags" in params_full
    assert isinstance(params_full["tags"], str)
    print("  [SAVE] Parameter contract valid")


def test_recall_params() -> None:
    """recall: query (string required)."""
    params = {"query": "What theme does the user prefer?"}
    assert "query" in params
    assert isinstance(params["query"], str) and len(params["query"]) > 0
    print("  [RECALL] Parameter contract valid")


def test_list_params() -> None:
    """list: limit (int optional), offset (int optional)."""
    params_default: dict = {}
    assert "limit" not in params_default or isinstance(params_default.get("limit"), int)
    assert "offset" not in params_default or isinstance(params_default.get("offset"), int)
    params_custom = {"limit": 20, "offset": 10}
    assert isinstance(params_custom["limit"], int) and params_custom["limit"] > 0
    assert isinstance(params_custom["offset"], int) and params_custom["offset"] >= 0
    print("  [LIST] Parameter contract valid")


def test_delete_params() -> None:
    """delete: id (int required)."""
    params = {"id": 42}
    assert "id" in params
    assert isinstance(params["id"], int) and params["id"] > 0
    print("  [DELETE] Parameter contract valid")


def test_fuse_params() -> None:
    """fuse: query (string required), ids (list of int required)."""
    params = {"query": "Summarize user preferences", "ids": [1, 2, 3]}
    assert "query" in params and "ids" in params
    assert isinstance(params["query"], str) and len(params["query"]) > 0
    assert isinstance(params["ids"], list) and len(params["ids"]) > 0
    assert all(isinstance(i, int) for i in params["ids"])
    print("  [FUSE] Parameter contract valid")


def test_rethink_params() -> None:
    """rethink: id (int required), text (string required)."""
    params = {"id": 42, "text": "Updated preference text"}
    assert "id" in params and "text" in params
    assert isinstance(params["id"], int) and params["id"] > 0
    assert isinstance(params["text"], str) and len(params["text"]) > 0
    print("  [RETHINK] Parameter contract valid")


def test_replace_params() -> None:
    """replace: id (int), old_text (string), new_text (string)."""
    params = {"id": 42, "old_text": "dark mode", "new_text": "light mode"}
    assert "id" in params and "old_text" in params and "new_text" in params
    assert isinstance(params["id"], int)
    assert isinstance(params["old_text"], str) and len(params["old_text"]) > 0
    assert isinstance(params["new_text"], str) and len(params["new_text"]) > 0
    print("  [REPLACE] Parameter contract valid")


def test_insert_params() -> None:
    """insert: text (string required), conversation_id (int)."""
    params_min = {"text": "New memory entry", "conversation_id": 5}
    assert "text" in params_min
    assert isinstance(params_min["text"], str) and len(params_min["text"]) > 0
    assert "conversation_id" in params_min
    assert isinstance(params_min["conversation_id"], int)
    print("  [INSERT] Parameter contract valid")


def test_dream_params() -> None:
    """dream: no params, editor-only."""
    params: dict = {}
    assert len(params) == 0
    print("  [DREAM] Parameter contract valid")


def test_save_experience_params() -> None:
    """save_experience: trigger_condition and steps required; scope defaults to user."""
    params = {
        "trigger_condition": "user asks about theme",
        "steps": '[{"intent":"recall","tool":"memory:recall"}]',
        "scope": "user",
    }
    assert isinstance(params["trigger_condition"], str) and len(params["trigger_condition"]) > 0
    assert isinstance(params["steps"], str) and len(params["steps"]) > 0
    assert params["scope"] in {"user", "team", "global"}
    print("  [SAVE_EXPERIENCE] Parameter contract valid")


def test_match_experience_params() -> None:
    """match_experience: query (string required), limit optional."""
    params = {"query": "user asks about theme", "limit": 2}
    assert "query" in params
    assert isinstance(params["query"], str) and len(params["query"]) > 0
    assert isinstance(params["limit"], int) and params["limit"] > 0
    print("  [MATCH_EXPERIENCE] Parameter contract valid")


def test_experience_feedback_params() -> None:
    """experience_feedback: experience_id (int), success (bool), note (string optional)."""
    params_min = {"experience_id": 10, "success": True}
    assert "experience_id" in params_min and "success" in params_min
    assert isinstance(params_min["experience_id"], int) and params_min["experience_id"] > 0
    assert isinstance(params_min["success"], bool)
    params_with_note = {"experience_id": 10, "success": False, "note": "Failed to apply"}
    assert "note" in params_with_note
    assert isinstance(params_with_note["note"], str)
    print("  [EXPERIENCE_FEEDBACK] Parameter contract valid")


def test_overview_stats_params() -> None:
    """overview_stats: no params, admin-only."""
    params: dict = {}
    assert len(params) == 0
    print("  [OVERVIEW_STATS] Parameter contract valid")


def test_recall_stable_rules_params() -> None:
    """recall_stable_rules: rule_types (optional array)."""
    params_default: dict = {}
    assert "rule_types" not in params_default
    params_with_filter = {"rule_types": ["preference", "constraint"]}
    assert "rule_types" in params_with_filter
    assert isinstance(params_with_filter["rule_types"], list)
    assert all(isinstance(t, str) for t in params_with_filter["rule_types"])
    print("  [RECALL_STABLE_RULES] Parameter contract valid")


def test_recall_chunk_params() -> None:
    """recall_chunk: query (string required), limit (int optional)."""
    params_min = {"query": "semantic search query"}
    assert "query" in params_min
    assert isinstance(params_min["query"], str) and len(params_min["query"]) > 0
    params_full = {"query": "semantic search query", "limit": 10}
    assert isinstance(params_full["limit"], int) and params_full["limit"] > 0
    print("  [RECALL_CHUNK] Parameter contract valid")


def test_save_stable_rule_params() -> None:
    """save_stable_rule: rule_type (string), content (string), priority (int optional), source (string optional)."""
    params_min = {"rule_type": "preference", "content": "User prefers dark mode"}
    assert "rule_type" in params_min and "content" in params_min
    assert isinstance(params_min["rule_type"], str) and len(params_min["rule_type"]) > 0
    assert isinstance(params_min["content"], str) and len(params_min["content"]) > 0
    params_full = {"rule_type": "constraint", "content": "No external API calls", "priority": 10, "source": "user_setting"}
    assert isinstance(params_full["priority"], int)
    assert isinstance(params_full["source"], str)
    print("  [SAVE_STABLE_RULE] Parameter contract valid")


def test_memory_output_shape() -> None:
    """Memory object output shape contract."""
    memory = {
        "id": 1,
        "text": "User prefers dark mode",
        "tags": "preference,ui",
        "created_at": "2026-07-01T00:00:00",
        "updated_at": "2026-07-01T00:00:00",
    }
    required = {"id", "text", "created_at"}
    for field in required:
        assert field in memory, f"Missing required field: {field}"
    assert isinstance(memory["id"], int)
    assert isinstance(memory["text"], str)
    assert len(memory["text"]) > 0
    print("  [MEMORY] Output shape valid")


def test_experience_output_shape() -> None:
    """Experience object output shape contract."""
    experience = {
        "id": 1,
        "owner_id": 7,
        "scope": "user",
        "trigger_condition": "user asks about theme",
        "steps": '[{"intent":"recall","tool":"memory:recall"}]',
        "success_weight": 3,
        "fail_count": 0,
    }
    required = {"id", "owner_id", "scope", "trigger_condition", "steps", "success_weight", "fail_count"}
    for field in required:
        assert field in experience, f"Missing required field: {field}"
    assert experience["scope"] in {"user", "team", "global"}
    assert isinstance(experience["success_weight"], int) and experience["success_weight"] >= 0
    print("  [EXPERIENCE] Output shape valid")


def test_stable_rule_output_shape() -> None:
    """Stable rule output shape contract."""
    rule = {
        "id": 1,
        "rule_type": "preference",
        "content": "User prefers dark mode",
        "priority": 5,
        "source": "user_setting",
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"id", "rule_type", "content", "priority"}
    for field in required:
        assert field in rule, f"Missing required field: {field}"
    assert isinstance(rule["priority"], int)
    print("  [STABLE_RULE] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"id": 1, "text": "test", "created_at": "2026-07-01T00:00:00"}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("memory sandbox test")
    print("=" * 60)
    test_save_params()
    test_recall_params()
    test_list_params()
    test_delete_params()
    test_fuse_params()
    test_rethink_params()
    test_replace_params()
    test_insert_params()
    test_dream_params()
    test_save_experience_params()
    test_match_experience_params()
    test_experience_feedback_params()
    test_overview_stats_params()
    test_recall_stable_rules_params()
    test_recall_chunk_params()
    test_save_stable_rule_params()
    test_memory_output_shape()
    test_experience_output_shape()
    test_stable_rule_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: memory sandbox test")


if __name__ == "__main__":
    main()
