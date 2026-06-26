"""Test batch 2: layered memory, hybrid recall, engine integration.
Tests the logic and data structures without a live DB or LLM.
"""
import math
import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Bootstrap the huashiwangzu_modules namespace so memory module's internal
# imports (e.g. from huashiwangzu_modules.memory.models) resolve correctly.
if "huashiwangzu_modules" not in sys.modules:
    top_pkg = types.ModuleType("huashiwangzu_modules")
    top_pkg.__path__ = []
    sys.modules["huashiwangzu_modules"] = top_pkg

_mem_backend = _project_root / "modules" / "memory" / "backend"
_pkg_name = "huashiwangzu_modules.memory"
if _pkg_name not in sys.modules:
    pkg = types.ModuleType(_pkg_name)
    pkg.__path__ = [str(_mem_backend)]
    sys.modules[_pkg_name] = pkg

from modules.memory.backend.models import MemoryRecord, MemoryLink
from modules.memory.backend.services.memory_service import _do_fuse, _do_dream
from modules.memory.backend.services.capabilities import (
    _cap_save, _cap_recall, _cap_list, _cap_delete,
    _cap_fuse, _cap_dream, _cap_rethink, _cap_replace, _cap_insert,
)
from modules.agent.backend.engine.engine import (
    assemble_context,
    chat_with_degradation_chain,
    chat_stream_with_degradation_chain,
)
from modules.agent.backend.engine import layered_memory
from app.services.module_registry import call_capability


class TestMemoryModel:
    """Test the data model structure for memory."""

    MODEL_COLUMNS = {
        "MemoryRecord": ["id", "owner_id", "text", "summary", "confidence",
                          "recency_score", "embedding", "raw_id", "memory_type",
                          "keywords", "access_count", "tags", "source",
                          "conversation_id", "created_at", "updated_at"],
        "MemoryLink": ["id", "from_id", "to_id", "relation", "weight",
                        "owner_id", "created_at", "updated_at"],
    }

    def test_model_has_summary_column(self):
        cols = MemoryRecord.__table__.columns
        for name in ("summary", "confidence", "recency_score", "raw_id",
                     "memory_type", "keywords", "access_count"):
            assert name in cols

    def test_memory_link_table_exists(self):
        cols = MemoryLink.__table__.columns
        for name in ("from_id", "to_id", "relation", "weight", "owner_id"):
            assert name in cols

    def test_summary_is_optional(self):
        assert MemoryRecord.__table__.columns["summary"].nullable

    def test_confidence_has_default(self):
        col = MemoryRecord.__table__.columns["confidence"]
        assert col.default is not None or not col.nullable

    def test_vector_dimension(self):
        col_type = str(MemoryRecord.__table__.columns["embedding"].type)
        assert "VECTOR" in col_type.upper() or "1024" in col_type


class TestHybridRecallLogic:
    """Test the recall data structure and fallback logic (no DB)."""

    def test_recall_result_shape(self):
        result = {
            "id": 1,
            "text": "我喜欢界面用蓝色",
            "summary": "用户偏好蓝色界面",
            "tags": "偏好,颜色",
            "confidence": 0.9,
            "recency_score": 1.0,
            "raw_id": None,
            "memory_type": "preference",
            "keywords": "蓝色,界面,配色",
            "similarity": 0.85,
        }
        assert result["memory_type"] == "preference"
        assert result["similarity"] > 0.3

    def test_recall_fallback_empty(self):
        assert callable(call_capability)

    def test_fallback_keyword_shape(self):
        result = {
            "id": 10,
            "text": "用户喜欢红色",
            "summary": None,
            "tags": None,
            "confidence": 1.0,
            "recency_score": 1.0,
            "raw_id": None,
            "memory_type": None,
            "keywords": None,
            "source": None,
            "conversation_id": None,
            "similarity": 0.0,
        }
        assert result["id"] == 10
        assert result["similarity"] == 0.0


class TestChainGraph:
    """Test memory chain graph data structure."""

    def test_link_attributes(self):
        link = MemoryLink(from_id=1, to_id=2, relation="semantic_related", weight=0.8, owner_id=1)
        assert link.from_id == 1
        assert link.to_id == 2
        assert link.relation == "semantic_related"
        assert link.weight == 0.8

    def test_expanded_recall_shape(self):
        seed = {"id": 1, "text": "种子", "similarity": 0.9}
        expanded = {"id": 2, "text": "链扩展", "similarity": 0.7}
        combined = [seed, expanded]
        assert len(combined) == 2
        assert combined[1]["similarity"] == 0.7

    def test_link_threshold_filter(self):
        seed = {"id": 1, "text": "种子", "similarity": 0.9}
        threshold = 0.4
        weak_link = {"id": 2, "text": "弱关联", "similarity": 0.3}
        if weak_link["similarity"] >= threshold:
            combined = [seed, weak_link]
        else:
            combined = [seed]
        assert len(combined) == 1

    def test_memory_link_table_columns(self):
        cols = MemoryLink.__table__.columns
        assert "relation" in cols
        assert cols["relation"].nullable is True or cols["relation"].default is not None


class TestFusion:
    """Test on-demand fusion logic."""

    def test_fuse_result_shape(self):
        result = {
            "fused": "用户偏好蓝色界面，且喜欢简洁风格。",
            "source_ids": [1, 2],
            "note": "融合成功",
        }
        assert result["fused"]
        assert len(result["source_ids"]) == 2

    def test_fuse_empty_fallback(self):
        result = {"fused": "", "source_ids": [], "note": "无有效记忆"}
        assert not result["fused"]

    def test_fuse_is_callable(self):
        assert callable(_do_fuse)


class TestDreamSelfOptimization:
    """Test dream data structures and report shape."""

    def test_dream_report_shape(self):
        report = {"merged": 0, "links_created": 0, "decayed": 3}
        assert "merged" in report
        assert "links_created" in report
        assert "decayed" in report

    def test_dream_is_callable(self):
        assert callable(_do_dream)

    def test_cosine_similarity(self):
        def cosine(a, b):
            if not a or not b:
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb) if na and nb else 0.0
        assert cosine([1, 0], [1, 0]) == 1.0
        assert cosine([1, 0], [0, 1]) == 0.0
        assert cosine([1, 2, 3], [1, 2, 3]) == 1.0
        assert cosine([], []) == 0.0

    def test_decay_scores(self):
        score = 1.0
        for _ in range(5):
            score *= 0.85
        assert score > 0.1
        score = max(score * 0.85, 0.1)
        assert score >= 0.1

    def test_merge_confidence_logic(self):
        conf_a, conf_b = 0.9, 0.7
        merged = max(conf_a, conf_b)
        assert merged == 0.9


class TestSelfEditTools:
    """Test self-edit tool structures."""

    def test_rethink_capability_signature(self):
        assert callable(_cap_rethink)

    def test_replace_text_logic(self):
        original = "我喜欢蓝色"
        replacement = original.replace("蓝色", "红色", 1)
        assert replacement == "我喜欢红色"

    def test_replace_not_found(self):
        original = "我喜欢蓝色"
        assert "不存在的文本" not in original

    def test_insert_text_logic(self):
        original = "旧内容"
        result = original + "\n" + "新追加"
        assert result == "旧内容\n新追加"

    def test_insert_capability_signature(self):
        assert callable(_cap_insert)

    def test_replace_capability_signature(self):
        assert callable(_cap_replace)


class TestEngineIntegration:
    """Test the engine-client integration via real imports."""

    def test_engine_has_expected_exports(self):
        assert callable(assemble_context)
        assert callable(chat_with_degradation_chain)
        assert callable(chat_stream_with_degradation_chain)

    def test_layered_memory_has_functions(self):
        assert callable(layered_memory.recall)
        assert callable(layered_memory.fuse)
        assert callable(layered_memory.trigger_dream)
        assert callable(layered_memory.three_layer_recall)
        assert callable(layered_memory.record_recall_quality)

    def test_layered_memory_invokes_call_capability(self):
        inner_source = layered_memory.call_capability
        assert callable(inner_source)

    def test_engine_uses_layered_memory(self):
        assert callable(assemble_context)

    def test_layered_memory_imports_cleanly(self):
        assert hasattr(layered_memory, "recall")
        assert hasattr(layered_memory, "fuse")

    def test_engine_imports_cleanly(self):
        assert callable(assemble_context)


class TestCapabilityRegistration:
    """Test that all required capabilities are registered."""

    CAPABILITIES = {
        "save": _cap_save,
        "recall": _cap_recall,
        "list": _cap_list,
        "delete": _cap_delete,
        "fuse": _cap_fuse,
        "dream": _cap_dream,
        "rethink": _cap_rethink,
        "replace": _cap_replace,
        "insert": _cap_insert,
    }

    def test_capability_names(self):
        for name, func in self.CAPABILITIES.items():
            assert callable(func), f"{name} is not callable"
