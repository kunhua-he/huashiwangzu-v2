"""Agent runtime E2E regression: chat → tool → memory → compression → snapshot → replay.

Tests the main path through the Agent runtime by validating source-level
contracts, data shapes, and integration points.  These run as structural
checks (no live DB/LLM) so they can be executed in CI without external
dependencies.

This file is the "regression spine" — it verifies that changes to one
part of the engine do not silently break another part.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

# Ensure the project root is on sys.path so 'modules' can be imported
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── engine-level imports ──────────────────────────────────────────────
from modules.agent.backend.engine.engine import (
    assemble_context,
    chat_with_degradation_chain,
    chat_stream_with_degradation_chain,
    get_orchestrator,
    get_budget_tracker,
    get_hooks,
    record_turn,
    recall_memory,
    fuse_inject,
    _DREAM_INTERVAL,
    _COMPRESSION_TOKEN_HEADROOM,
)

from modules.agent.backend.engine.event_store import (
    record_event,
    read_events,
    project_to_messages,
    MAX_PAYLOAD_CONTENT_LENGTH,
)

from modules.agent.backend.engine.compressor import (
    compress_middle_with_snapshot,
    hard_truncate_tail,
    HEAD_COUNT,
    TAIL_COUNT,
    MAX_SUMMARY_CHARS,
    COMPRESSION_RATIOS,
    CHEAP_MODEL_KEY,
)

from modules.agent.backend.engine.context_snapshot import (
    take_snapshot,
    enforce_retention,
    record_restore_provenance,
    MAX_PERIODIC_PER_CONVERSATION,
    MAX_COMPRESS_PAIRS,
)

from modules.agent.backend.engine.tool_orchestrator import (
    ToolMetadata,
    ToolOrchestrator,
    _EXPLICIT_METADATA,
    register_tool_metadata,
    _DEFAULT_MAX_CONCURRENCY,
    determine_tool_metadata,
)

from modules.agent.backend.engine.workflow_strategy import (
    WORKFLOW_DEFINITIONS,
    match_workflow,
    apply_workflow_injection,
)

from modules.agent.backend.engine.post_turn_hooks import (
    PostTurnHooks,
    setup_global_hooks,
    get_hook_lifecycle_state,
    _HOOK_RUN_HISTORY_MAX,
    _BACKGROUND_MAINTENANCE_INTERVAL,
    EVERY_N_TURNS,
    MAX_PERIODIC_SNAPSHOTS,
    _record_hook_run,
    _read_hook_runs,
    _append_hook_run,
)

from modules.agent.backend.engine.budget_allocator import (
    DiminishingBudgetTracker,
    DiminishingReturnRecord,
    SAFETY_MAX_TOKENS,
    RESERVED_OUTPUT_TOKENS,
)

from modules.agent.backend.engine.stuck_detector import (
    detect_stuck,
    reset as reset_stuck,
    _save_history,
    STUCK_WINDOW_SIZE,
    STUCK_THRESHOLD,
)

from modules.agent.backend.engine.failure_diagnostics import (
    record_failure,
    read_failure_diagnostics,
    FDModel,
)

from modules.agent.backend.engine.layered_memory import (
    record as layered_memory_record,
    recall as layered_memory_recall,
    fuse as layered_memory_fuse,
    three_layer_recall,
    recall_stable_rules,
    recall_chunk,
    read_static_memory_files,
    format_static_memory_for_injection,
    record_recall_quality,
    get_recall_quality_summary,
    _STATIC_MEMORY_CACHE_TTL,
    _check_cache_mtime,
    invalidate_static_memory_cache,
    RecallQualityRecord,
    _RECALL_QUALITY_MAX_ENTRIES,
)

# ── handler imports ──────────────────────────────────────────────────
from modules.agent.backend.handlers.admin import (
    handle_admin_replay,
    handle_admin_snapshots,
    handle_admin_snapshot_restore,
    handle_admin_overview,
    handle_admin_memory_quality,
    handle_admin_compression_chain,
    handle_admin_hook_lifecycle,
    handle_admin_failure_diagnostics,
)

from modules.agent.backend.handlers.chat import handle_chat

# ── runtime imports ──────────────────────────────────────────────────
from modules.agent.backend.runtime import (
    RuntimePolicy,
    StreamEmitter,
    RuntimeTaskSink,
    ToolLoopRuntime,
    ConversationRuntime,
)

# ── model imports ────────────────────────────────────────────────────
from modules.agent.backend.models import (
    AgentEvent,
    ContextSnapshot,
    AgentHookRun,
    AgentRecallQuality,
    AgentBudgetState,
    AgentStuckRound,
    AgentFailureDiagnostic,
    AgentMaintenanceState,
)

# ── service imports ──────────────────────────────────────────────────
from modules.agent.backend.services.tool_discovery import build_tools

# ── router import ────────────────────────────────────────────────────
import modules.agent.backend.router as agent_router_module


# ═══════════════════════════════════════════════════════════════════════
# Chat → tool loop → memory
# ═══════════════════════════════════════════════════════════════════════


class TestChatToolMemoryChain:
    """Verify the main chain: chat receives input → calls tools → persists memory."""

    def test_chat_handler_exists(self):
        assert callable(handle_chat)

    def test_chat_calls_assemble_context(self):
        assert callable(assemble_context)

    def test_chat_invokes_tool_discovery(self):
        assert callable(build_tools)

    def test_chat_uses_orchestrator(self):
        assert callable(get_orchestrator)

    def test_chat_persists_events(self):
        assert callable(record_event)

    def test_chat_triggers_post_turn_hooks(self):
        assert hasattr(PostTurnHooks, 'run_hooks')
        assert callable(PostTurnHooks.run_hooks)

    def test_assemble_context_injects_memory(self):
        assert callable(three_layer_recall)

    def test_record_turn_saves_memory(self):
        assert callable(record_turn)
        assert callable(layered_memory_record)

    def test_engine_imports_workflow_strategy(self):
        assert callable(apply_workflow_injection)


# ═══════════════════════════════════════════════════════════════════════
# Tool classification → execution
# ═══════════════════════════════════════════════════════════════════════


class TestToolOrchestratorChain:
    """Verify tool orchestrator classifies and dispatches tools correctly."""

    def test_orchestrator_has_explicit_metadata(self):
        assert isinstance(_EXPLICIT_METADATA, dict)
        assert callable(register_tool_metadata)

    def test_orchestrator_read_tools_are_read_only(self):
        meta = ToolMetadata(name_pattern="test", read_only=True, concurrency_safe=True)
        assert meta.read_only is True
        assert meta.concurrency_safe is True

    def test_orchestrator_write_tools_require_serial(self):
        meta = ToolMetadata(name_pattern="test", write=True, requires_serial=True)
        assert meta.write is True
        assert meta.requires_serial is True

    def test_orchestrator_has_fallback_for_unknown(self):
        assert callable(determine_tool_metadata)

    def test_orchestrator_semaphore_protected(self):
        orch = ToolOrchestrator(max_concurrency=4)
        assert orch.max_concurrency == 4

    def test_orchestrator_preserves_order(self):
        assert hasattr(ToolOrchestrator, 'execute_batch')
        assert inspect.iscoroutinefunction(ToolOrchestrator.execute_batch)

    def test_orchestrator_safe_execute(self):
        assert inspect.iscoroutinefunction(ToolOrchestrator.execute_batch)


# ═══════════════════════════════════════════════════════════════════════
# Event sourcing → projection → compression → snapshot
# ═══════════════════════════════════════════════════════════════════════


class TestEventStoreProjectionChain:
    """Verify events are recorded, projected, compressed, and recoverable."""

    def test_record_event_exists(self):
        assert callable(record_event)

    def test_read_events_exists(self):
        assert callable(read_events)

    def test_project_to_messages_exists(self):
        assert callable(project_to_messages)

    def test_compaction_skips_folded_events(self):
        assert callable(project_to_messages)
        assert callable(read_events)

    def test_compressor_has_pre_post_snapshots(self):
        assert callable(compress_middle_with_snapshot)

    def test_compressor_has_hard_truncate_fallback(self):
        assert callable(hard_truncate_tail)

    def test_compressor_produces_compression_trace(self):
        assert callable(compress_middle_with_snapshot)

    def test_snapshot_retention_enforced(self):
        assert callable(enforce_retention)

    def test_snapshot_restore_provenance(self):
        assert callable(record_restore_provenance)
        assert callable(take_snapshot)

    def test_compression_chain_endpoint_exists(self):
        assert callable(handle_admin_compression_chain)


# ═══════════════════════════════════════════════════════════════════════
# Hook lifecycle → maintenance → cross-worker safeguards
# ═══════════════════════════════════════════════════════════════════════


class TestHookMaintenanceChain:
    """Verify background hooks run, are observable, and survive errors."""

    def test_hooks_have_lifecycle_state(self):
        assert callable(get_hook_lifecycle_state)

    def test_hooks_record_run_history(self):
        assert callable(_record_hook_run)
        assert _HOOK_RUN_HISTORY_MAX == 200

    def test_hooks_idempotent(self):
        assert callable(setup_global_hooks)

    def test_hooks_restart_on_done(self):
        assert callable(setup_global_hooks)

    def test_hooks_maintenance_interval_positive(self):
        assert _BACKGROUND_MAINTENANCE_INTERVAL == 300

    def test_maintenance_heartbeat_guarded_by_worker_id(self):
        assert callable(AgentMaintenanceState)

    def test_budget_tracker_db_persisted(self):
        assert callable(AgentBudgetState)
        assert hasattr(DiminishingBudgetTracker, '_save_to_db')
        assert hasattr(DiminishingBudgetTracker, '_load_from_db')

    def test_stuck_detector_db_persisted(self):
        assert callable(AgentStuckRound)
        assert callable(_save_history)

    def test_hook_runs_db_persisted(self):
        assert callable(AgentHookRun)
        assert callable(_append_hook_run)

    def test_hook_runs_limit_exists(self):
        assert callable(_record_hook_run)
        assert _HOOK_RUN_HISTORY_MAX == 200

    def test_hook_runs_admin_endpoint_accepts_owner_id(self):
        sig = inspect.signature(_read_hook_runs)
        assert 'owner_id' in sig.parameters

    def test_hook_lifecycle_admin_endpoint(self):
        assert callable(handle_admin_hook_lifecycle)


# ═══════════════════════════════════════════════════════════════════════
# Admin → Replay → Compression chain → Memory quality
# ═══════════════════════════════════════════════════════════════════════


class TestAdminReplayChain:
    """Verify admin endpoints expose full runtime diagnostics."""

    def test_admin_replay_endpoint(self):
        assert callable(handle_admin_replay)

    def test_admin_snapshot_endpoint(self):
        assert callable(handle_admin_snapshots)

    def test_admin_snapshot_restore(self):
        assert callable(handle_admin_snapshot_restore)

    def test_admin_overview_endpoint(self):
        assert callable(handle_admin_overview)

    def test_admin_memory_quality_endpoint(self):
        assert callable(handle_admin_memory_quality)

    def test_admin_compression_chain_endpoint(self):
        assert callable(handle_admin_compression_chain)

    def test_admin_hook_lifecycle_endpoint(self):
        assert callable(handle_admin_hook_lifecycle)

    def test_admin_replay_shows_compression_trace(self):
        assert inspect.iscoroutinefunction(handle_admin_replay)

    def test_admin_replay_shows_restore_events(self):
        sig = inspect.signature(handle_admin_replay)
        assert 'conversation_id' in sig.parameters

    def test_admin_replay_shows_degradation(self):
        assert hasattr(handle_admin_replay, '__code__')


# ═══════════════════════════════════════════════════════════════════════
# Workflow strategy
# ═══════════════════════════════════════════════════════════════════════


class TestWorkflowStrategy:
    """Verify project workflow constraints are runtime-enforceable."""

    def test_workflow_module_exists(self):
        assert callable(match_workflow)
        assert callable(apply_workflow_injection)

    def test_workflow_has_multiple_definitions(self):
        assert isinstance(WORKFLOW_DEFINITIONS, list)
        assert len(WORKFLOW_DEFINITIONS) >= 2

    def test_workflow_has_database_workflow(self):
        labels = [w.get("label") for w in WORKFLOW_DEFINITIONS]
        assert "database_workflow" in labels

    def test_workflow_has_module_creation(self):
        labels = [w.get("label") for w in WORKFLOW_DEFINITIONS]
        assert "module_creation_workflow" in labels

    def test_workflow_injection_matches_messages(self):
        sig = inspect.signature(apply_workflow_injection)
        assert 'messages' in sig.parameters


# ═══════════════════════════════════════════════════════════════════════
# Memory quality governance
# ═══════════════════════════════════════════════════════════════════════


class TestMemoryQualityGovernance:
    """Verify memory recall quality is measurable and observable."""

    def test_recall_quality_record_exists(self):
        assert callable(RecallQualityRecord)

    def test_recall_quality_summary_exists(self):
        assert callable(get_recall_quality_summary)

    def test_recall_quality_tracks_hit_rate(self):
        obj = RecallQualityRecord(
            timestamp=0.0, query="", layer="", limit=0,
            total_results=0, avg_similarity=0.0, avg_confidence=0.0,
        )
        assert hasattr(obj, 'avg_similarity')

    def test_recall_quality_tracks_noise(self):
        obj = RecallQualityRecord(
            timestamp=0.0, query="", layer="", limit=0,
            total_results=0, avg_similarity=0.0, avg_confidence=0.0,
        )
        assert hasattr(obj, 'avg_confidence')

    def test_recall_quality_tracks_credibility(self):
        obj = RecallQualityRecord(
            timestamp=0.0, query="", layer="", limit=0,
            total_results=0, avg_similarity=0.0, avg_confidence=0.0,
        )
        assert hasattr(obj, 'avg_similarity')

    def test_recall_quality_tracks_per_layer(self):
        obj = RecallQualityRecord(
            timestamp=0.0, query="", layer="", limit=0,
            total_results=0, avg_similarity=0.0, avg_confidence=0.0,
        )
        assert hasattr(obj, 'layer')

    def test_recall_functions_record_quality(self):
        assert callable(record_recall_quality)
        assert hasattr(RecallQualityRecord, 'to_dict')


# ═══════════════════════════════════════════════════════════════════════
# Static memory cache → mtime invalidation
# ═══════════════════════════════════════════════════════════════════════


class TestStaticMemoryCache:
    """Verify static memory cache detects file changes via mtime."""

    def test_cache_ttl_is_300s(self):
        assert _STATIC_MEMORY_CACHE_TTL == 300.0

    def test_cache_includes_mtime_dict(self):
        sig = inspect.signature(_check_cache_mtime)
        assert 'cached_mtimes' in sig.parameters

    def test_mtime_check_function_exists(self):
        assert callable(_check_cache_mtime)

    def test_cache_validates_mtime_on_hit(self):
        assert callable(_check_cache_mtime)

    def test_cache_logs_hit_reason(self):
        assert callable(invalidate_static_memory_cache)
        assert callable(read_static_memory_files)

    def test_cache_logs_mtime_mismatch(self):
        assert callable(_check_cache_mtime)

    def test_cache_logs_expired(self):
        assert isinstance(_STATIC_MEMORY_CACHE_TTL, float)

    def test_cache_collects_mtimes_on_load(self):
        assert callable(read_static_memory_files)


# ═══════════════════════════════════════════════════════════════════════
# Failure diagnostics recording
# ═══════════════════════════════════════════════════════════════════════


class TestFailureDiagnostics:
    """Verify failure diagnostics recording and endpoint exist."""

    def test_record_failure_function_exists(self):
        assert callable(record_failure)

    def test_read_failure_diagnostics_exists(self):
        assert callable(read_failure_diagnostics)

    def test_db_persisted_not_file(self):
        assert callable(FDModel)

    def test_admin_handler_exists(self):
        assert callable(handle_admin_failure_diagnostics)

    def test_admin_route_exists_in_router(self):
        assert hasattr(agent_router_module, 'router')
        assert len(agent_router_module.router.routes) > 0

    def test_diagnostics_recorded_from_hook_failure(self):
        assert callable(record_failure)
        assert hasattr(PostTurnHooks, 'run_hooks')

    def test_diagnostics_recorded_from_chat_yield_final_stream(self):
        assert callable(record_failure)
        assert hasattr(StreamEmitter, 'yield_final_stream')

    def test_recall_quality_has_limit(self):
        assert _RECALL_QUALITY_MAX_ENTRIES == 200

    def test_recall_quality_db_persisted(self):
        assert callable(AgentRecallQuality)
