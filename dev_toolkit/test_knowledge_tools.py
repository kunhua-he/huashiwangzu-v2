from __future__ import annotations

from dev_toolkit import knowledge_source_gap, knowledge_source_manifest_audit, knowledge_tools


def test_knowledge_tool_component_exports_pipeline_and_source_gap_tools() -> None:
    names = {tool.name for tool in knowledge_tools.tool_definitions()}

    assert names == {
        "knowledge_pipeline_snapshot",
        "knowledge_source_gap_snapshot",
        "knowledge_source_manifest_audit",
        "knowledge_source_manifest_summary",
        "knowledge_source_manifest_scan",
        "knowledge_source_manifest_enqueue",
    }
    assert knowledge_tools.handles_tool("knowledge_pipeline_snapshot") is True
    assert knowledge_tools.handles_tool("knowledge_source_gap_snapshot") is True
    assert knowledge_tools.handles_tool("knowledge_source_manifest_audit") is True
    assert knowledge_tools.handles_tool("knowledge_source_manifest_summary") is True
    assert knowledge_tools.handles_tool("knowledge_source_manifest_scan") is True
    assert knowledge_tools.handles_tool("knowledge_source_manifest_enqueue") is True


def test_source_gap_extension_normalization_defaults_to_documents_and_images() -> None:
    extensions = knowledge_source_gap.normalize_extensions(None)

    assert "pdf" in extensions
    assert "docx" in extensions
    assert "jpg" in extensions
    assert "png" in extensions


def test_source_gap_extension_normalization_accepts_dotted_values() -> None:
    extensions = knowledge_source_gap.normalize_extensions([".PDF", "jpg", "pdf", ""])

    assert extensions == ["jpg", "pdf"]


def test_source_gap_root_id_normalization_ignores_invalid_values() -> None:
    assert knowledge_source_gap.normalize_int_list(["48", "bad", -1, 0, 1141]) == [48, 1141]


def test_source_manifest_audit_stage_normalization_defaults_to_pipeline_stages() -> None:
    stages = knowledge_source_manifest_audit.normalize_stage_list(None)

    assert "source_validate" in stages
    assert "parse_index" in stages
    assert "raw_vision" in stages
    assert "relations" in stages


def test_source_manifest_audit_stage_normalization_deduplicates() -> None:
    assert knowledge_source_manifest_audit.normalize_stage_list(["parse_index", "", "parse_index"]) == ["parse_index"]


def test_summarize_stage_metrics_extracts_relation_and_model_stats() -> None:
    summary = knowledge_tools._summarize_stage_metrics(
        [
            {
                "stage": "relations",
                "status": "done",
                "model_used": "",
                "model_profile": "",
                "duration_ms": 1000,
                "metrics_json": {
                    "timing": {
                        "vector_candidates": 12,
                        "entity_candidates": 5,
                        "merged_candidates": 14,
                        "db_commit_ms": 40,
                    }
                },
            },
            {
                "stage": "fusion",
                "status": "done",
                "model_used": "gpt-5.5-knowledge",
                "duration_ms": 2000,
                "metrics_json": {
                    "timing": {
                        "llm_ms": 1700,
                        "db_write_ms": 30,
                    }
                },
            },
        ]
    )

    assert summary["window_size"] == 2
    assert summary["status_counts"] == {"done": 2}
    assert summary["duration_ms_by_stage"]["relations"] == {"count": 1, "median": 1000, "p90": 1000, "max": 1000}
    assert summary["duration_ms_by_model"]["gpt-5.5-knowledge"]["median"] == 2000
    assert summary["key_metrics"]["vector_candidates"]["median"] == 12
    assert summary["key_metrics"]["db_commit_ms"]["median"] == 40
    assert summary["key_metrics"]["llm_ms"]["median"] == 1700
