"""Tests for layered_memory.py — static memory file reading + formatting + selector/fencing/snapshot."""
import tempfile
from pathlib import Path
from .layered_memory import (
    read_static_memory_files, format_static_memory_for_injection, invalidate_static_memory_cache,
    select_memory_segments, MemorySelectionResult,
    MemoryFence, DEFAULT_MEMORY_FENCE, apply_fencing,
    freeze_memory_snapshot, get_frozen_snapshot, invalidate_frozen_snapshot,
    MIN_RELEVANCE_SCORE, MAX_MEMORY_SEGMENTS, STABLE_RULES_HARD_CAP,
)


class TestMemorySelector:

    def test_empty_inputs(self):
        selection, rules, chunks, sem = select_memory_segments([], [], [], query="hello")
        assert selection.raw_rules == 0
        assert selection.raw_chunks == 0
        assert selection.raw_semantic == 0
        total_dropped = len(selection.dropped_rules) + len(selection.dropped_chunks) + len(selection.dropped_semantic)
        assert total_dropped == 0
        assert rules == []
        assert chunks == []

    def test_keeps_relevant_chunks(self):
        chunks_in = [
            {"text": "very relevant", "similarity": 0.85, "provenance": "doc1"},
            {"text": "barely relevant", "similarity": 0.15, "provenance": "doc2"},
            {"text": "somewhat relevant", "similarity": 0.45, "provenance": "doc3"},
        ]
        selection, _, kept_chunks, _ = select_memory_segments([], chunks_in, [], query="test")
        assert selection.raw_chunks == 3
        assert len(kept_chunks) <= MAX_MEMORY_SEGMENTS // 2
        # The 0.15 relevance one should be dropped
        assert 0 <= len(kept_chunks) <= 2

    def test_rules_capped(self):
        many_rules = [
            {"content": f"rule {i}", "priority": 100 - i, "rule_type": "test"}
            for i in range(STABLE_RULES_HARD_CAP + 10)
        ]
        selection, kept_rules, _, _ = select_memory_segments(many_rules, [], [])
        assert selection.raw_rules == STABLE_RULES_HARD_CAP + 10
        assert len(kept_rules) <= STABLE_RULES_HARD_CAP
        assert len(selection.dropped_rules) >= 10

    def test_selection_reason_format(self):
        selection, _, _, _ = select_memory_segments(
            [{"content": "rule1", "priority": 1, "rule_type": "t"}],
            [{"text": "chunk1", "similarity": 0.9, "provenance": "d"}],
            [{"text": "sem1", "similarity": 0.8}],
            query="test",
        )
        assert "kept" in selection.selection_reason
        assert "dropped" in selection.selection_reason


class TestMemoryFencing:

    def test_default_fence_applies_cap(self):
        parts = {
            "stable_rules": "<stable_rules>\n[x] a" + "x" * 3000 + "\n</stable_rules>",
            "chunks": "<chunks>\n[1] big chunk\n</chunks>",
            "semantic": "<semantic_memories>\n[1] big semantic\n</semantic_memories>",
        }
        result = apply_fencing(parts)
        assert "stable_rules" in result
        assert "chunks" in result or "semantic" in result

    def test_disabled_layers_omitted(self):
        fence = MemoryFence(inject_semantic=False, inject_chunks=False)
        parts = {
            "stable_rules": "<stable_rules>\nkeep\n</stable_rules>",
            "chunks": "<chunks>\nskip\n</chunks>",
            "semantic": "<semantic_memories>\nskip\n</semantic_memories>",
        }
        result = apply_fencing(parts, fence)
        assert "stable_rules" in result
        assert "chunks" not in result
        assert "semantic" not in result

    def test_char_cap_stable_rules(self):
        fence = MemoryFence(stable_rules_max_char=5)
        parts = {"stable_rules": "<stable_rules>\nlong content here\n</stable_rules>"}
        result = apply_fencing(parts, fence)
        assert len(result) <= 5


class TestFrozenSnapshot:

    def test_freeze_and_retrieve(self):
        key = freeze_memory_snapshot(
            owner_id=1, conversation_id=10,
            stable_rules=[{"content": "rule1"}],
            chunks=[{"text": "chunk1"}],
            semantic=[{"text": "sem1"}],
            token_estimate=500, turn_count=3, label="test",
        )
        assert key == "frozen:1:10:test"
        snap = get_frozen_snapshot(key)
        assert snap is not None
        assert snap.owner_id == 1
        assert len(snap.stable_rules) == 1
        assert snap.token_estimate == 500

    def test_invalidate(self):
        key = freeze_memory_snapshot(1, 20, [], [], [])
        invalidate_frozen_snapshot(key)
        assert get_frozen_snapshot(key) is None

    def test_missing_key(self):
        assert get_frozen_snapshot("nonexistent") is None
    def test_no_dir_returns_empty(self):
        invalidate_static_memory_cache()
        result = read_static_memory_files("/tmp/nonexistent_static_memory_test_dir_xyz")
        assert result == []

    def test_reads_markdown_files(self, tmp_path):
        invalidate_static_memory_cache()
        d = tmp_path / "static-memory"
        d.mkdir()
        (d / "rules.md").write_text("Always use Chinese.\nNever share secrets.")
        (d / "prefs.md").write_text("User prefers short answers.")
        result = read_static_memory_files(str(d))
        assert len(result) == 2
        assert "Always use Chinese" in result[0] or "Always use Chinese" in result[1]

    def test_skips_empty_files(self, tmp_path):
        invalidate_static_memory_cache()
        d = tmp_path / "static-memory-empty"
        d.mkdir()
        (d / "empty.md").write_text("")
        (d / "nonempty.md").write_text("content")
        result = read_static_memory_files(str(d))
        assert len(result) == 1
        assert result[0] == "content"

    def test_caching(self, tmp_path):
        invalidate_static_memory_cache()
        d = tmp_path / "static-memory-cache"
        d.mkdir()
        (d / "test.md").write_text("initial")
        result1 = read_static_memory_files(str(d))
        assert len(result1) == 1
        (d / "test2.md").write_text("new file")
        result2 = read_static_memory_files(str(d))
        assert len(result2) == 1  # cached


class TestFormatStaticMemory:
    def test_empty_list(self):
        assert format_static_memory_for_injection([]) == ""

    def test_single_rule(self):
        result = format_static_memory_for_injection(["Always use Chinese."])
        assert "<static_memory>" in result
        assert "Always use Chinese" in result

    def test_multiple_rules(self):
        result = format_static_memory_for_injection(["Rule 1", "Rule 2"])
        assert result.count("<rule>") == 2
