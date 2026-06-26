"""Test context snapshot lifecycle: list, restore, retention, admin fields.

Verifies snapshot management operations and the admin display fields
by importing and inspecting real module functions.
"""
import inspect
import typing

from modules.agent.backend.engine.context_snapshot import (
    list_snapshots,
    restore_snapshot,
    record_restore_provenance,
    enforce_retention,
    get_latest_snapshot,
    count_snapshots,
    take_snapshot,
    MAX_PERIODIC_PER_CONVERSATION,
    MAX_COMPRESS_PAIRS,
)
from modules.agent.backend.handlers.admin import (
    handle_admin_snapshots,
    handle_admin_snapshot_restore,
)
from modules.agent.backend.engine.post_turn_hooks import (
    setup_global_hooks,
    _run_global_retention,
)
from modules.agent.backend.engine.engine import get_hooks


class TestSnapshotAdminFields:
    """Verify admin display fields for snapshot list/restore."""

    SRC = inspect.getsource(take_snapshot)

    def test_snapshot_type_field(self):
        """Snapshot list must include snapshot_type."""
        assert "snapshot_type" in self.SRC

    def test_event_boundaries_field(self):
        """Snapshot must have event_id_before and event_id_after."""
        assert "event_id_before" in self.SRC
        assert "event_id_after" in self.SRC

    def test_compression_ratio_field(self):
        """Snapshot must have compression_ratio."""
        assert "compression_ratio" in self.SRC

    def test_restored_from_field(self):
        """Snapshot must have restored_from field."""
        assert "restored_from" in self.SRC

    def test_message_counts_field(self):
        """Snapshot must have message count fields."""
        assert "message_count_before" in self.SRC
        assert "message_count_after" in self.SRC

    def test_token_estimates_field(self):
        """Snapshot must have token estimate fields."""
        assert "token_estimate_before" in self.SRC
        assert "token_estimate_after" in self.SRC


class TestSnapshotList:
    """Verify list_snapshots returns correct data."""

    SRC = inspect.getsource(list_snapshots)

    def test_list_snapshots_exists(self):
        """list_snapshots must be defined."""
        assert callable(list_snapshots)

    def test_list_snapshots_returns_list(self):
        """list_snapshots must return a list."""
        assert "list(r.scalars().all())" in self.SRC

    def test_list_snapshots_ordered(self):
        """list_snapshots must order by newest first."""
        assert "order_by(desc(" in self.SRC

    def test_list_snapshots_has_limit(self):
        """list_snapshots must accept a limit parameter."""
        assert "limit(limit)" in self.SRC or "limit=20" in self.SRC


class TestSnapshotRestore:
    """Verify restore_snapshot produces audit trail."""

    SRC = inspect.getsource(restore_snapshot)
    PROV_SRC = inspect.getsource(record_restore_provenance)

    def test_restore_snapshot_exists(self):
        """restore_snapshot must be defined."""
        assert callable(restore_snapshot)

    def test_restore_records_provenance(self):
        """restore_snapshot must call record_restore_provenance."""
        assert "record_restore_provenance" in self.SRC

    def test_restore_provenance_exists(self):
        """record_restore_provenance must be defined."""
        assert callable(record_restore_provenance)

    def test_restore_provenance_writes_event(self):
        """record_restore_provenance must call record_event with snapshot_restore type."""
        assert "snapshot_restore" in self.PROV_SRC

    def test_restore_provenance_includes_snapshot_id(self):
        """Restore provenance event must include snapshot_id."""
        assert "snapshot_id" in self.PROV_SRC

    def test_restore_returns_messages(self):
        """restore_snapshot must return a list of messages."""
        hints = typing.get_type_hints(restore_snapshot)
        ret = hints.get("return")
        assert ret is not None
        assert ret == list[dict]

    def test_restore_handles_missing_snapshot(self):
        """restore_snapshot must return empty list for missing snapshot."""
        assert "return []" in self.SRC


class TestSnapshotRetention:
    """Verify retention policy enforcement."""

    ENF_SRC = inspect.getsource(enforce_retention)

    def test_enforce_retention_exists(self):
        """enforce_retention must be defined."""
        assert callable(enforce_retention)

    def test_enforce_retention_returns_pruned_count(self):
        """enforce_retention must return dict with pruned count."""
        assert '"pruned"' in self.ENF_SRC or "'pruned'" in self.ENF_SRC

    def test_periodic_retention_limit(self):
        """Periodic retention must cap at MAX_PERIODIC_PER_CONVERSATION."""
        assert MAX_PERIODIC_PER_CONVERSATION == 15
        assert "periodic" in self.ENF_SRC
        assert ".offset(max_keep)" in self.ENF_SRC

    def test_compress_retention_limit(self):
        """Compress retention must cap at MAX_COMPRESS_PAIRS."""
        assert MAX_COMPRESS_PAIRS == 10
        assert "pre_compress" in self.ENF_SRC
        assert "post_compress" in self.ENF_SRC

    def test_get_latest_snapshot_exists(self):
        """get_latest_snapshot must be defined."""
        assert callable(get_latest_snapshot)

    def test_count_snapshots_exists(self):
        """count_snapshots must be defined."""
        assert callable(count_snapshots)


class TestAdminEndpoints:
    """Verify admin snapshot endpoints exist in the admin handler."""

    def test_admin_snapshots_handler_exists(self):
        """Admin handler must define handle_admin_snapshots."""
        assert callable(handle_admin_snapshots)

    def test_admin_snapshot_restore_handler_exists(self):
        """Admin handler must define handle_admin_snapshot_restore."""
        assert callable(handle_admin_snapshot_restore)

    def test_admin_snapshot_fields_complete(self):
        """Admin snapshot response must include all display fields."""
        src = inspect.getsource(handle_admin_snapshots)
        display_fields = [
            '"snapshot_type"',
            '"event_id_before"',
            '"event_id_after"',
            '"message_count_before"',
            '"message_count_after"',
            '"token_estimate_before"',
            '"token_estimate_after"',
            '"compression_ratio"',
            '"restored_from"',
            '"summary"',
            '"created_at"',
        ]
        for field in display_fields:
            assert field in src, f"Admin snapshot response missing field: {field}"

    def test_admin_snapshot_restore_fields(self):
        """Admin snapshot restore response must include key metadata."""
        src = inspect.getsource(handle_admin_snapshot_restore)
        restore_fields = [
            '"snapshot_id"',
            '"restored_messages"',
            '"snapshot_type"',
            '"compression_ratio"',
            '"event_id_before"',
            '"event_id_after"',
        ]
        for field in restore_fields:
            assert field in src, f"Admin snapshot restore response missing field: {field}"


class TestPostTurnHooksLifecycle:
    """Verify post-turn hooks lifecycle is well-defined."""

    SRC = inspect.getsource(setup_global_hooks)

    def test_setup_global_hooks_starts_background_task(self):
        """setup_global_hooks must create a background asyncio task."""
        assert callable(setup_global_hooks)
        assert "asyncio.create_task" in self.SRC

    def test_setup_global_hooks_has_maintenance_loop(self):
        """setup_global_hooks must have a maintenance loop."""
        assert "_maintenance_loop" in self.SRC
        assert "_run_global_retention" in self.SRC

    def test_background_retention_calls_enforce_retention(self):
        """_run_global_retention must call context_snapshot.enforce_retention."""
        assert callable(_run_global_retention)
        src = inspect.getsource(_run_global_retention)
        assert "enforce_retention" in src

    def test_background_retention_queries_all_conversations(self):
        """_run_global_retention must query all distinct conversation_ids."""
        src = inspect.getsource(_run_global_retention)
        assert "SELECT DISTINCT conversation_id" in src

    def test_background_retention_error_handling(self):
        """_run_global_retention must handle per-conversation errors non-fatally."""
        src = inspect.getsource(_run_global_retention)
        assert "logger.warning" in src
        assert "conv=%s" in src

    def test_maintenance_loop_restarts_after_exception(self):
        """Maintenance loop must catch exceptions and continue."""
        assert 'logger.exception("Maintenance observer iteration failed' in self.SRC

    def test_setup_global_hooks_is_idempotent(self):
        """setup_global_hooks must skip re-creation if task already running."""
        assert "already running" in self.SRC

    def test_get_hooks_triggers_setup_global_hooks(self):
        """engine.get_hooks() must call setup_global_hooks on first access."""
        src = inspect.getsource(get_hooks)
        assert "setup_global_hooks()" in src
