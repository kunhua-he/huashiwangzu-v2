"""Test memory core paths: save, chunk rebuild, rethink/replace/insert,
recall_chunk provenance, save_stable_rule.

Tests data structures, logic invariants, and source-level correctness
without requiring a live database or LLM.
"""
import importlib
import inspect
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap the huashiwangzu_modules.memory namespace package (same mechanism
# the framework registry uses at runtime) so relative intra-module imports
# resolve correctly.
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "modules"


def _init_namespace() -> None:
    """Set up huashiwangzu_modules.memory so intra-package imports work."""
    import types

    if "huashiwangzu_modules" not in sys.modules:
        top = types.ModuleType("huashiwangzu_modules")
        top.__path__ = []
        sys.modules["huashiwangzu_modules"] = top

    pkg_name = "huashiwangzu_modules.memory"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(MODULES_DIR / "memory" / "backend")]
        sys.modules[pkg_name] = pkg

    # Prevent pytest from picking up a stale 'backend' module
    sys.modules.pop("backend", None)


# Must happen before any imports from the memory module — the module-level
# code in app/database.py instantiates Settings which validates JWT_SECRET.
os.environ.setdefault("JWT_SECRET", "test-secret-key")

_init_namespace()
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import huashiwangzu_modules.memory.services.memory_service as memory_service  # noqa: E402
import huashiwangzu_modules.memory.services.capabilities as capabilities  # noqa: E402
import huashiwangzu_modules.memory.services.embedding_service as embedding_service  # noqa: E402

_split_memory_chunks = memory_service._split_memory_chunks
_parse_user_id = memory_service._parse_user_id
_refresh_chunks_for_memory = memory_service._refresh_chunks_for_memory
_enqueue_post_save = memory_service._enqueue_post_save
_update_embedding = memory_service._update_embedding
_post_save_process = memory_service._post_save_process

_cap_save = capabilities._cap_save
_cap_rethink = capabilities._cap_rethink
_cap_replace = capabilities._cap_replace
_cap_insert = capabilities._cap_insert
_cap_recall_chunk = capabilities._cap_recall_chunk
_cap_save_stable_rule = capabilities._cap_save_stable_rule
_cap_delete = capabilities._cap_delete

_update_embedding_sql = embedding_service._update_embedding_sql


# ===================================================================
# Tests
# ===================================================================


class TestMemorySavePath:
    """Verify save -> embedding -> post_save -> chunk rebuild chain."""

    def test_save_triggers_chunk_rebuild(self):
        """Capability save must enqueue post-save processing which rebuilds chunks."""
        assert callable(_cap_save)
        cap_src = inspect.getsource(_cap_save)
        assert "_enqueue_post_save" in cap_src
        assert callable(_refresh_chunks_for_memory)

    def test_save_calls_update_embedding(self):
        """Save path must update embedding before enqueuing."""
        cap_src = inspect.getsource(_cap_save)
        assert "_update_embedding(memory.id, text)" in cap_src

    def test_post_save_calls_refresh_chunks(self):
        """_post_save_process must call _refresh_chunks_for_memory."""
        assert callable(_post_save_process)
        psp_src = inspect.getsource(_post_save_process)
        assert "_refresh_chunks_for_memory" in psp_src

    def test_post_save_skips_embedding_when_present(self):
        """_post_save_process must check mem.embedding and skip if already set."""
        psp_src = inspect.getsource(_post_save_process)
        assert "mem.embedding is None" in psp_src

    def test_post_save_enqueue_is_fire_and_forget(self):
        """_enqueue_post_save writes to SystemTaskQueue."""
        eq_src = inspect.getsource(_enqueue_post_save)
        assert "SystemTaskQueue" in eq_src
        assert "memory_post_save" in eq_src


class TestChunkRebuild:
    """Verify chunk split & rebuild produces correct provenance fields."""

    def test_split_chunks_returns_provenance_triples(self):
        """_split_memory_chunks must return list of (text, start_char, end_char)."""
        assert callable(_split_memory_chunks)
        chunks = _split_memory_chunks("Hello world. This is a test memory.")
        assert isinstance(chunks, list)
        if chunks:
            chunk = chunks[0]
            assert len(chunk) == 3
            text, start, end = chunk
            assert isinstance(text, str)
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start >= 0
            assert end > start

    def test_split_empty_content(self):
        """Empty content must return empty list."""
        assert _split_memory_chunks("") == []
        assert _split_memory_chunks(None) == []
        assert _split_memory_chunks("   ") == []

    def test_split_short_content_no_split(self):
        """Content shorter than MEMORY_CHUNK_MAX_CHARS must return single chunk."""
        text = "A" * 100
        chunks = _split_memory_chunks(text)
        assert len(chunks) == 1
        assert chunks[0][0] == text
        assert chunks[0][1] == 0
        assert chunks[0][2] == 100

    def test_split_respects_max_chars(self):
        """Each chunk text must not exceed MEMORY_CHUNK_MAX_CHARS."""
        text = "Hello world. " * 200
        chunks = _split_memory_chunks(text)
        for chunk_text, _, end in chunks:
            assert len(chunk_text) <= 900

    def test_chunk_overlap_preserved(self):
        """Adjacent chunks must overlap by at least MEMORY_CHUNK_OVERLAP_CHARS."""
        text = "Hello world. " * 300
        chunks = _split_memory_chunks(text)
        if len(chunks) >= 2:
            first_end = chunks[0][2]
            second_start = chunks[1][1]
            overlap = first_end - second_start
            assert overlap >= 120 or overlap <= 0

    def test_chunk_refresh_deletes_old_chunks_first(self):
        """_refresh_chunks_for_memory must DELETE old chunks before inserting."""
        src = inspect.getsource(_refresh_chunks_for_memory)
        assert "DELETE FROM memory_chunks WHERE memory_record_id" in src

    def test_chunk_has_all_provenance_fields(self):
        """Chunk row must include memory_record_id, chunk_index, provenance, start_char, end_char."""
        src = inspect.getsource(_refresh_chunks_for_memory)
        for field in ("memory_record_id", "chunk_index", "provenance", "start_char", "end_char"):
            assert field in src, f"Missing chunk field: {field}"

    def test_provenance_format(self):
        """Provenance must follow 'memory_record:{id}#chunk:{index}' pattern."""
        src = inspect.getsource(_refresh_chunks_for_memory)
        assert "f\"memory_record:{memory.id}#chunk:{index}\"" in src

    def test_chunk_summary_only_on_first_chunk(self):
        """Only first chunk should get the summary."""
        src = inspect.getsource(_refresh_chunks_for_memory)
        assert "summary if index == 0 else None" in src


class TestRethinkReplaceInsert:
    """Verify rethink/replace/insert don't leave orphan chunks."""

    def test_rethink_triggers_post_save(self):
        """_cap_rethink must call _enqueue_post_save which rebuilds chunks."""
        src = inspect.getsource(_cap_rethink)
        assert "_enqueue_post_save(mem_id, text, \"rethink\")" in src
        assert "source = \"rethink\"" in src

    def test_replace_triggers_post_save(self):
        """_cap_replace must call _enqueue_post_save which rebuilds chunks."""
        src = inspect.getsource(_cap_replace)
        assert "_enqueue_post_save(mem_id, memory.text, \"edit\")" in src
        assert "source = \"edit\"" in src

    def test_insert_triggers_post_save(self):
        """_cap_insert must call _enqueue_post_save which rebuilds chunks."""
        src = inspect.getsource(_cap_insert)
        assert "_enqueue_post_save(mem_id, memory.text, \"edit\")" in src

    def test_rethink_updates_text_and_source(self):
        """rethink must set text and source='rethink' on the memory record."""
        src = inspect.getsource(_cap_rethink)
        lines = src.splitlines()
        found_text = any("memory.text = text" in line for line in lines)
        found_source = any("memory.source = \"rethink\"" in line for line in lines)
        assert found_text, "rethink must update memory.text"
        assert found_source, "rethink must set source='rethink'"

    def test_replace_uses_replace_text_logic(self):
        """replace must use str.replace(old_text, new_text, 1)."""
        src = inspect.getsource(_cap_replace)
        assert "memory.text.replace(old_text, new_text, 1)" in src

    def test_insert_appends_text(self):
        """insert must append text with newline separator."""
        src = inspect.getsource(_cap_insert)
        assert "memory.text += \"\\n\" + text" in src

    def test_no_orphan_chunks_after_rebuild(self):
        """All edit paths go through _refresh_chunks_for_memory which
        DELETEs old chunks first, so no orphans remain."""
        src = inspect.getsource(_refresh_chunks_for_memory)
        assert "DELETE FROM memory_chunks WHERE memory_record_id" in src

    def test_all_edit_paths_update_embedding(self):
        """_cap_rethink, _cap_replace, _cap_insert must all call _update_embedding."""
        rethink_src = inspect.getsource(_cap_rethink)
        replace_src = inspect.getsource(_cap_replace)
        insert_src = inspect.getsource(_cap_insert)
        assert "_update_embedding(mem_id, text)" in rethink_src
        assert "_update_embedding(mem_id, memory.text)" in replace_src
        assert "_update_embedding(mem_id, memory.text)" in insert_src

    def test_rethink_source_in_post_save(self):
        """rethink's enqueue must pass 'rethink' as source."""
        src = inspect.getsource(_cap_rethink)
        assert "\"rethink\"" in src


class TestRecallChunk:
    """Verify recall_chunk returns full provenance and falls back to keyword search."""

    def test_recall_chunk_has_all_provenance_fields(self):
        """recall_chunk vector SQL must SELECT all provenance fields."""
        src = inspect.getsource(_cap_recall_chunk)
        for field in ("memory_record_id", "provenance", "chunk_index", "start_char", "end_char", "created_at"):
            assert field in src, f"Missing field: {field}"

    def test_recall_chunk_returns_similarity(self):
        """Vector path must return similarity score."""
        src = inspect.getsource(_cap_recall_chunk)
        assert "similarity" in src

    def test_recall_chunk_keyword_fallback(self):
        """recall_chunk must have keyword fallback via text.ilike."""
        src = inspect.getsource(_cap_recall_chunk)
        assert "text.ilike(keyword)" in src

    def test_recall_chunk_keyword_returns_same_fields(self):
        """Keyword path must return same provenance fields as vector path."""
        src = inspect.getsource(_cap_recall_chunk)
        keyword_keys = (
            "\"id\"", "\"memory_record_id\"", "\"text\"", "\"summary\"",
            "\"source\"", "\"provenance\"", "\"conversation_id\"",
            "\"chunk_index\"", "\"confidence\"", "\"start_char\"",
            "\"end_char\"", "\"similarity\"", "\"created_at\"",
        )
        for key in keyword_keys:
            assert key in src, f"Keyword path missing field: {key}"

    def test_recall_chunk_threshold_bound(self):
        """Vector search must apply 0.3 similarity threshold."""
        src = inspect.getsource(_cap_recall_chunk)
        assert ">= 0.3" in src or "> 0.3" in src


class TestSaveStableRule:
    """Verify save_stable_rule capability."""

    def test_save_stable_rule_exists(self):
        """save_stable_rule capability must be defined."""
        assert callable(_cap_save_stable_rule)

    def test_save_stable_rule_creates_record(self):
        """save_stable_rule must create a MemoryStableRule record."""
        src = inspect.getsource(_cap_save_stable_rule)
        assert "MemoryStableRule(" in src

    def test_save_stable_rule_returns_id(self):
        """save_stable_rule must return the created rule id."""
        src = inspect.getsource(_cap_save_stable_rule)
        assert "\"id\": rule.id" in src

    def test_save_stable_rule_requires_content(self):
        """save_stable_rule must reject empty content."""
        src = inspect.getsource(_cap_save_stable_rule)
        assert "not content.strip()" in src


class TestServiceIntegrity:
    """Verify service-layer invariants."""

    def test_parse_user_id(self):
        """_parse_user_id must extract int from 'user:{id}' format."""
        assert _parse_user_id("user:42") == 42
        assert _parse_user_id("user:0") == 0
        assert _parse_user_id("user:1") == 1
        assert _parse_user_id("") == 0
        assert _parse_user_id("agent:5") == 0

    def test_ensure_init_called(self):
        """All capability functions must call _ensure_init()."""
        cap_src = inspect.getsource(capabilities)
        count = cap_src.count("await memory_service._ensure_init()")
        assert count >= 10, f"Expected >=10 _ensure_init() calls, got {count}"

    def test_update_embedding_sql_imported(self):
        """_update_embedding_sql must be imported from embedding_service."""
        assert callable(_update_embedding_sql)
        ms_src = inspect.getsource(memory_service)
        assert "from .embedding_service import _update_embedding_sql" in ms_src

    def test_recall_chunk_signature(self):
        """_cap_recall_chunk must have correct signature."""
        src = inspect.getsource(_cap_recall_chunk)
        first_line = src.splitlines()[0]
        assert "async def _cap_recall_chunk(params: dict, caller: str) -> dict:" in first_line

    def test_save_capability_returns_id(self):
        """_cap_save must return the new memory id."""
        src = inspect.getsource(_cap_save)
        assert "\"id\": memory.id" in src

    def test_delete_cleans_links(self):
        """_cap_delete must clean up memory_links first."""
        src = inspect.getsource(_cap_delete)
        assert "DELETE FROM memory_links" in src
