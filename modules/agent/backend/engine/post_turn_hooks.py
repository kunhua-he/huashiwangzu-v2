"""Post-turn hook chain for agent conversation loop.

Runs asynchronously after each conversation turn without blocking
the main conversation flow. All hooks fire via create_task so the
caller returns immediately.

## Hook chain (fixed order, each is non-blocking)

1. **memory_distill** — Extract facts from the current turn → save to memory.
2. **profile_evolve** — Submit a profile evolution task to SystemTaskQueue.
3. **prompt_suggestion** — Analyse turn for prompt improvement opportunities.
4. **context_snapshot** — Take a periodic snapshot every N turns.
5. **cleanup_archive** — Prune stale periodic snapshots beyond retention.

Each hook is individually wrapped in try/except so a single failure
never cascades to other hooks or the main conversation flow.

Background maintenance (``setup_global_hooks``) runs on a fixed 5-min
interval to enforce retention policies across all conversations.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, desc, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentEvent, ContextSnapshot, AgentHookRun, AgentMaintenanceState
from .context_snapshot import take_snapshot

logger = logging.getLogger("v2.agent").getChild("engine.post_turn_hooks")

# Periodic snapshot: take a snapshot every N turns per conversation.
EVERY_N_TURNS = 3

# How many periodic snapshots to keep per conversation (newest retained).
MAX_PERIODIC_SNAPSHOTS = 10

# Background maintenance interval (seconds)
_BACKGROUND_MAINTENANCE_INTERVAL = 300  # 5 minutes

# Background maintenance lifecycle tracking (per-worker control state)
_background_maintenance_task: asyncio.Task | None = None
_background_maintenance_run_count: int = 0

# ── Hook lifecycle governance (persisted via DB for cross-worker) ─────
_HOOK_RUN_HISTORY_MAX = 200


async def _read_hook_runs(db: AsyncSession, owner_id: int | None = None) -> list[dict]:
    q = select(AgentHookRun)
    if owner_id is not None and owner_id > 0:
        q = q.where(AgentHookRun.owner_id == owner_id)
    q = q.order_by(desc(AgentHookRun.created_at)).limit(_HOOK_RUN_HISTORY_MAX)
    r = await db.execute(q)
    return [
        {
            "hook_name": row.hook_name,
            "success": row.success,
            "duration_ms": row.duration_ms,
            "detail": row.detail or "",
            "timestamp": row.created_at.timestamp() if row.created_at else 0,
            "conversation_id": row.conversation_id,
        }
        for row in r.scalars().all()
    ]


async def _append_hook_run(
    db: AsyncSession, owner_id: int, conversation_id: int | None, record: dict,
) -> None:
    db.add(AgentHookRun(
        owner_id=owner_id,
        conversation_id=conversation_id,
        hook_name=record.get("hook_name", ""),
        success=record.get("success", False),
        duration_ms=record.get("duration_ms", 0.0),
        detail=record.get("detail", "")[:500],
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()


async def _read_maintenance_state(db: AsyncSession) -> dict:
    """Read lifecycle state from the single-row DB table."""
    r = await db.execute(
        select(AgentMaintenanceState).where(AgentMaintenanceState.id == 1)
    )
    row = r.scalar_one_or_none()
    if not row:
        return {
            "maintenance_status": "stopped",
            "run_count": 0,
            "started_at": None,
            "last_heartbeat_at": None,
            "worker_id": "",
        }
    return {
        "maintenance_status": row.maintenance_status,
        "run_count": row.run_count,
        "started_at": row.started_at.timestamp() if row.started_at else None,
        "last_heartbeat_at": row.last_heartbeat_at.timestamp() if row.last_heartbeat_at else None,
        "worker_id": row.worker_id,
    }


async def _upsert_maintenance_state(db: AsyncSession, state: dict) -> None:
    """Upsert the single-row maintenance state (cross-worker safe).

    WARNING: This overwrites *started_at* if present in *state*.
    Do NOT use this for periodic heartbeats — use ``_try_claim_leadership``
    or ``_increment_and_heartbeat`` instead to preserve the original
    ``started_at`` value.
    """
    stmt = pg_insert(AgentMaintenanceState).values(
        id=1,
        maintenance_status=state.get("maintenance_status", "stopped"),
        worker_id=state.get("worker_id", ""),
        started_at=state.get("started_at"),
        last_heartbeat_at=state.get("last_heartbeat_at", datetime.now(timezone.utc)),
        run_count=state.get("run_count", 0),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "maintenance_status": stmt.excluded.maintenance_status,
            "worker_id": stmt.excluded.worker_id,
            "started_at": stmt.excluded.started_at,
            "last_heartbeat_at": stmt.excluded.last_heartbeat_at,
            "run_count": stmt.excluded.run_count,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def get_hook_lifecycle_state(db: AsyncSession, owner_id: int | None = None) -> dict:
    """Return observable hook lifecycle state for admin health check.

    Source of truth is the DB row (cross-worker consistent).  Per-worker
    in-memory state is returned under a separate ``local_observer_running``
    field so it cannot be mistaken for the global truth.
    """
    state = await _read_maintenance_state(db)
    # DB-backed global state — consistent across workers
    state["maintenance_running"] = (state.get("maintenance_status") == "running")
    state["local_observer_running"] = (
        _background_maintenance_task is not None and not _background_maintenance_task.done()
    )
    state["maintenance_started_at"] = state.pop("started_at", None)
    state["maintenance_run_count"] = state.pop("run_count", None)
    all_runs = await _read_hook_runs(db, owner_id)
    state["recent_hook_runs"] = all_runs[:20]  # all_runs is DESC-ordered (newest first)
    state["hook_names"] = ["memory_distill", "profile_evolve", "context_snapshot", "cleanup_archive", "prompt_suggestion", "background_review"]
    # lifecycle stats
    total = len(all_runs)
    failures = [r for r in all_runs if not r.get("success")]
    state["lifecycle"] = {
        "total_hook_runs": total,
        "failed_hook_runs": len(failures),
        "success_rate": round((total - len(failures)) / max(total, 1), 3),
        "per_hook": {},
    }
    for name in state["hook_names"]:
        runs = [r for r in all_runs if r.get("hook_name") == name]
        hook_fails = [r for r in runs if not r.get("success")]
        state["lifecycle"]["per_hook"][name] = {
            "total": len(runs),
            "failed": len(hook_fails),
            "avg_duration_ms": round(sum(r.get("duration_ms", 0) for r in runs) / max(len(runs), 1), 1),
        }
    return state


async def get_lifecycle_chain(db: AsyncSession, conversation_id: int, limit: int = 50) -> list[dict]:
    """Return the lifecycle event chain for a conversation.

    Combines hook runs, snapshots, snapshots_restored, and maintenance
    events into a unified timeline.
    """
    from .event_store import read_events as _read_events
    from .context_snapshot import list_snapshots as _list_snapshots

    events = await _read_events(db, conversation_id)
    snapshots = await _list_snapshots(db, conversation_id, limit)

    chain: list[dict] = []
    # hook runs
    hook_runs = await _read_hook_runs(db)
    for hr in hook_runs:
        if hr.get("conversation_id") == conversation_id:
            chain.append({
                "type": "hook_run",
                "hook_name": hr["hook_name"],
                "success": hr["success"],
                "duration_ms": hr["duration_ms"],
                "timestamp": hr.get("timestamp", 0),
            })
    # compression traces from events
    for ev in events:
        if ev.event_type == "compression_trace":
            chain.append({
                "type": "compression_trace",
                "event_id": ev.id,
                "folded_count": ev.payload.get("folded_count", 0),
                "pre_snapshot_id": ev.payload.get("pre_snapshot_id"),
                "post_snapshot_id": ev.payload.get("post_snapshot_id"),
                "timestamp": ev.created_at.timestamp() if ev.created_at else 0,
            })
        elif ev.event_type == "snapshot_restore":
            chain.append({
                "type": "snapshot_restore",
                "event_id": ev.id,
                "snapshot_id": ev.payload.get("snapshot_id"),
                "timestamp": ev.created_at.timestamp() if ev.created_at else 0,
            })
    # snapshots
    for snap in snapshots:
        chain.append({
            "type": "snapshot",
            "snapshot_id": snap.id,
            "snapshot_type": snap.snapshot_type,
            "compression_ratio": snap.compression_ratio,
            "message_count_before": snap.message_count_before,
            "message_count_after": snap.message_count_after,
            "restored_from": snap.restored_from,
            "timestamp": snap.created_at.timestamp() if snap.created_at else 0,
        })
    chain.sort(key=lambda x: x.get("timestamp", 0))
    return chain[-limit:]


async def _record_hook_run(
    db: AsyncSession, owner_id: int, conversation_id: int | None,
    name: str, success: bool, duration_ms: float, detail: str = "",
) -> None:
    """Record a hook run for lifecycle observability (persisted via DB)."""
    await _append_hook_run(db, owner_id, conversation_id, {
        "hook_name": name,
        "success": success,
        "duration_ms": round(duration_ms, 1),
        "detail": detail[:200],
    })


async def _get_turn_count(db: AsyncSession, conversation_id: int) -> int:
    """Count assistant_msg events as a deterministic turn counter (cross-worker safe)."""
    r = await db.execute(
        select(func.count()).select_from(AgentEvent)
        .where(
            AgentEvent.conversation_id == conversation_id,
            AgentEvent.event_type == "assistant_msg",
        )
    )
    return r.scalar() or 0


class PostTurnHooks:
    """Fixed hook chain that runs after each conversation turn.

    Hooks are executed as fire-and-forget tasks via ``asyncio.create_task``.
    Each hook is individually wrapped in try/except so a single failure
    never cascades to other hooks or the main conversation flow.
    """

    async def run_hooks(
        self,
        db: AsyncSession,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
        tool_events: list[dict] | None = None,
        timeline: list[dict] | None = None,
    ) -> dict:
        """Run all post-turn hooks as fire-and-forget tasks.

        Returns a summary dict immediately without awaiting the hooks.
        The ``db`` session is **not** reused by the spawned tasks —
        each hook opens its own database session to avoid use-after-close
        on the caller's session.
        """
        tool_events = tool_events or []
        timeline = timeline or []

        summary: dict = {"hooks_run": [], "errors": {}}

        async def _safe_run(name: str, coro):
            _t0 = time.time()
            try:
                await coro
                _t1 = time.time()
                summary["hooks_run"].append(name)
                from app.database import AsyncSessionLocal as _ASL
                async with _ASL() as _db:
                    await _record_hook_run(_db, owner_id, conversation_id, name, True, (_t1 - _t0) * 1000)
            except Exception as exc:
                _t1 = time.time()
                logger.exception("Post-turn hook '%s' failed (non-fatal): %s", name, exc)
                summary["errors"][name] = str(exc)
                from app.database import AsyncSessionLocal as _ASL
                async with _ASL() as _db:
                    await _record_hook_run(_db, owner_id, conversation_id, name, False, (_t1 - _t0) * 1000, str(exc)[:200])
                from .failure_diagnostics import record_failure
                await record_failure("hook", f"run_{name}", type(exc).__name__, str(exc), conversation_id, owner_id)

        asyncio.create_task(
            _safe_run("memory_distill", self._hook_memory_distill(
                conversation_id, owner_id, messages, tool_events,
            ))
        )

        asyncio.create_task(
            _safe_run("profile_evolve", self._hook_profile_evolve(
                conversation_id, owner_id, messages,
            ))
        )

        asyncio.create_task(
            _safe_run("context_snapshot", self._hook_context_snapshot(
                conversation_id, owner_id, messages,
            ))
        )

        asyncio.create_task(
            _safe_run("cleanup_archive", self._hook_cleanup_archive(
                conversation_id,
            ))
        )

        asyncio.create_task(
            _safe_run("prompt_suggestion", self._hook_prompt_suggestion(
                conversation_id, owner_id, messages,
            ))
        )

        asyncio.create_task(
            _safe_run("background_review", self._hook_background_review(
                conversation_id, owner_id, messages, tool_events,
            ))
        )

        return summary

    async def _hook_memory_distill(
        self,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
        tool_events: list[dict],
    ) -> dict:
        """Extract facts from the recent conversation turn and save to memory.

        Delegates to ``engine.record_turn`` which handles extraction and
        persistence via the layered memory store.
        """
        logger.debug("memory_distill: conv=%s owner=%s", conversation_id, owner_id)

        from app.database import AsyncSessionLocal
        from .engine import record_turn

        async with AsyncSessionLocal() as session:
            result = await record_turn(session, conversation_id, owner_id, messages)
            return result

    async def _hook_profile_evolve(
        self,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
    ) -> None:
        """Submit a profile evolution task to ``SystemTaskQueue``.

        The ``profile_evolve`` task handler runs asynchronously and decides
        whether the latest turn warrants an update to the user's profile.
        Throttling (cooldown) is handled inside the task handler itself.
        """
        logger.debug("profile_evolve: conv=%s owner=%s", conversation_id, owner_id)

        from app.database import AsyncSessionLocal
        from app.models.system import SystemTaskQueue

        async with AsyncSessionLocal() as session:
            task = SystemTaskQueue(
                task_type="profile_evolve",
                parameters=json.dumps({
                    "conversation_id": conversation_id,
                    "owner_id": owner_id,
                }),
                status="pending",
                priority=0,
                module="agent",
                creator_id=owner_id,
            )
            session.add(task)
            await session.commit()

    async def _hook_prompt_suggestion(
        self,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
    ) -> None:
        """Record a lightweight suggestion when the assistant reply is too thin."""
        from app.database import AsyncSessionLocal
        from .event_store import record_event

        assistant_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                assistant_text = str(msg.get("content", "") or "").strip()
                break

        if not assistant_text or len(assistant_text) >= 120:
            return

        async with AsyncSessionLocal() as session:
            await record_event(
                session,
                conversation_id,
                "hook_prompt_suggestion",
                {
                    "owner_id": owner_id,
                    "assistant_length": len(assistant_text),
                    "suggestion": "assistant_reply_too_short",
                },
                llm_response_id=None,
            )

    async def _hook_context_snapshot(
        self,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
    ) -> None:
        """Take a periodic snapshot every ``EVERY_N_TURNS`` turns.

        Snapshots provide a recoverable checkpoint for replay and audit
        without incurring I/O overhead on every turn.
        Uses DB-backed assistant_msg count as turn counter (cross-worker safe).
        """
        from app.database import AsyncSessionLocal
        from .event_store import read_events

        async with AsyncSessionLocal() as session:
            counter = await _get_turn_count(session, conversation_id)
            if counter % EVERY_N_TURNS != 0:
                logger.debug(
                    "context_snapshot skipped (turn %s/%s): conv=%s",
                    counter, EVERY_N_TURNS, conversation_id,
                )
                return

            logger.debug("context_snapshot: conv=%s turn=%s", conversation_id, counter)
            events = await read_events(session, conversation_id)
            await take_snapshot(
                db=session,
                conversation_id=conversation_id,
                snapshot_type="periodic",
                messages=messages,
                events=events,
                summary=f"Periodic snapshot at turn {counter}",
            )

    async def _hook_cleanup_archive(
        self,
        conversation_id: int,
    ) -> None:
        """Clean up stale periodic snapshots beyond retention limit.

        Removes the oldest periodic snapshots when the count exceeds
        ``MAX_PERIODIC_SNAPSHOTS`` per conversation.
        """
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            try:
                r = await session.execute(
                    select(ContextSnapshot.id)
                    .where(
                        ContextSnapshot.conversation_id == conversation_id,
                        ContextSnapshot.snapshot_type == "periodic",
                    )
                    .order_by(desc(ContextSnapshot.id))
                    .offset(MAX_PERIODIC_SNAPSHOTS)
                )
                stale_ids = [row[0] for row in r.all()]
                if stale_ids:
                    await session.execute(
                        delete(ContextSnapshot).where(ContextSnapshot.id.in_(stale_ids))
                    )
                    await session.commit()
                    logger.info(
                        "cleanup_archive: removed %d stale periodic snapshots for conv=%s",
                        len(stale_ids), conversation_id,
                    )
            except Exception as exc:
                await session.rollback()
                logger.warning("cleanup_archive failed (non-fatal): %s", exc)

    async def _hook_background_review(
        self,
        conversation_id: int,
        owner_id: int,
        messages: list[dict],
        tool_events: list[dict],
    ) -> None:
        """Run a background review fork after each conversation turn.

        The review fork:
          - Uses a restricted tool set (memory + skill proposals only)
          - Does NOT interact with the user
          - Produces structured proposals stored in agent_review_results
          - Review fork proposals CANNOT directly modify skills

        Throttled: skips if the last N messages have no user content
        or if the conversation is too short (< 3 messages).
        """
        if len(messages) < 3:
            return

        has_user_msg = any(m.get("role") == "user" for m in messages[-3:])
        if not has_user_msg:
            return

        from ..services.review_service import run_background_review
        await run_background_review(
            conversation_id=conversation_id,
            owner_id=owner_id,
            messages=messages,
            tool_events=tool_events,
        )


_MAINTENANCE_INTERVAL = 300  # 5 minutes, must be > 0

_STALE_LEADERSHIP_SECONDS = _MAINTENANCE_INTERVAL * 2 + 60  # 660s = ~11min


async def _try_claim_leadership(db: AsyncSession) -> bool:
    """Atomically claim maintenance leadership via DB.

    Only succeeds when no other worker has a fresh heartbeat.
    Returns True if this worker is now the leader.
    Uses a single atomic UPDATE with conditional WHERE so multiple workers
    never run maintenance concurrently.
    """
    now = datetime.now(timezone.utc)
    worker_id = f"worker:{os.getpid()}"
    stale_threshold = now - timedelta(seconds=_STALE_LEADERSHIP_SECONDS)
    from sqlalchemy import text as _text
    r = await db.execute(
        _text("""
            UPDATE agent_maintenance_state
            SET maintenance_status = 'running',
                worker_id = :worker_id,
                last_heartbeat_at = :now,
                started_at = COALESCE(started_at, :now)
            WHERE id = 1
              AND (maintenance_status IN ('stopped', 'cancelled')
                   OR last_heartbeat_at IS NULL
                   OR last_heartbeat_at < :stale_threshold
                   OR (worker_id = :worker_id AND maintenance_status = 'running'))
            RETURNING 1
        """),
        {
            "worker_id": worker_id,
            "now": now,
            "stale_threshold": stale_threshold,
        },
    )
    await db.commit()
    return r.rowcount > 0


async def _increment_and_heartbeat(db: AsyncSession) -> None:
    """Increment run_count and refresh heartbeat for the current lease holder.

    The write is guarded by ``worker_id`` so a worker that lost leadership
    during a long maintenance cycle cannot overwrite the new leader's state.
    """
    now = datetime.now(timezone.utc)
    worker_id = f"worker:{os.getpid()}"
    from sqlalchemy import text as _text
    await db.execute(
        _text("""
            UPDATE agent_maintenance_state
            SET run_count = run_count + 1,
                last_heartbeat_at = :now
            WHERE id = 1
              AND worker_id = :worker_id
              AND maintenance_status = 'running'
        """),
        {"now": now, "worker_id": worker_id},
    )
    await db.commit()


async def _mark_maintenance_stopped(db: AsyncSession) -> None:
    """Mark maintenance as stopped (on cancellation/shutdown).

    Only succeeds when this worker is the current lease holder.
    Non-leader workers calling this is a no-op.
    """
    worker_id = f"worker:{os.getpid()}"
    from sqlalchemy import text as _text
    await db.execute(
        _text("""
            UPDATE agent_maintenance_state
            SET maintenance_status = 'stopped',
                last_heartbeat_at = NOW()
            WHERE id = 1
              AND worker_id = :worker_id
        """),
        {"worker_id": worker_id},
    )
    await db.commit()


def setup_global_hooks() -> None:
    """Register startup hooks for the post-turn system.

    Starts a background observer task that periodically enforces
    snapshot retention across all conversations.  The task uses a
    DB-based leader election (``agent_maintenance_state``, single-row)
    so that only one worker across the process pool runs the actual
    maintenance — others observe and skip.

    The observer runs on a fixed interval (``_MAINTENANCE_INTERVAL``
    seconds) and is wrapped in try/except so a single failure never
    kills the loop.

    Lifecycle state is persisted to the DB for cross-worker observability;
    per-worker counters are used only for local logging.
    """
    global _background_maintenance_task, _background_maintenance_run_count  # noqa: PLW0603

    if _background_maintenance_task is not None:
        if not _background_maintenance_task.done():
            logger.debug("setup_global_hooks: background task already running")
            return
        logger.warning("setup_global_hooks: previous background task finished, restarting")

    async def _maintenance_loop() -> None:
        global _background_maintenance_run_count  # 嵌套函数对模块全局 += 必须声明, 否则 UnboundLocalError
        logger.info(
            "Maintenance observer started (interval=%ss, EVERY_N_TURNS=%s, MAX_PERIODIC_SNAPSHOTS=%s)",
            _MAINTENANCE_INTERVAL, EVERY_N_TURNS, MAX_PERIODIC_SNAPSHOTS,
        )
        while True:
            try:
                await asyncio.sleep(_MAINTENANCE_INTERVAL)

                # Atomically claim leadership via DB
                # Only one worker across the process pool becomes the leader.
                try:
                    from app.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as _db:
                        is_leader = await _try_claim_leadership(_db)
                except Exception as _claim_exc:
                    logger.warning("Maintenance leadership claim failed: %s", _claim_exc)
                    continue

                if not is_leader:
                    logger.debug("Maintenance: another worker is leading, skipping cycle")
                    continue

                # We are the leader — run global retention
                _background_maintenance_run_count += 1
                result = await _run_global_retention()

                # Sync run_count and heartbeat to DB
                try:
                    from app.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as _db:
                        await _increment_and_heartbeat(_db)
                except Exception as _sync_exc:
                    logger.warning("Maintenance heartbeat sync failed: %s", _sync_exc)

                if result.get("total_pruned", 0) > 0:
                    logger.info(
                        "Maintenance iteration %d: pruned %d snapshots",
                        _background_maintenance_run_count, result["total_pruned"],
                    )
            except asyncio.CancelledError:
                logger.info(
                    "Maintenance observer cancelled (local run count: %d)",
                    _background_maintenance_run_count,
                )
                try:
                    from app.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as _db:
                        await _mark_maintenance_stopped(_db)
                except Exception:
                    logger.warning("Failed to mark maintenance stopped on cancel")
                break
            except Exception:
                logger.exception("Maintenance observer iteration failed (will retry)")

    _background_maintenance_task = asyncio.create_task(_maintenance_loop(), name="agent-hooks-maintenance")
    _background_maintenance_run_count = 0
    logger.info(
        "setup_global_hooks: post-turn hooks ready (EVERY_N_TURNS=%s, MAX_PERIODIC_SNAPSHOTS=%s)",
        EVERY_N_TURNS, MAX_PERIODIC_SNAPSHOTS,
    )


async def _run_global_retention() -> dict:
    """Enforce snapshot retention for all conversations that have snapshots.

    Queries ``agent_context_snapshots`` for distinct conversation IDs,
    then runs the retention policy on each.  Failures are non-fatal
    (logged per conversation).
    """
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    stats = {"conversations_checked": 0, "total_pruned": 0, "errors": 0}
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("SELECT DISTINCT conversation_id FROM agent_context_snapshots")
            )
            conv_ids = [row[0] for row in r.all()]
    except Exception as exc:
        logger.warning("Global retention: failed to query conversation IDs: %s", exc)
        return {"error": str(exc)}

    for conv_id in conv_ids:
        try:
            from .context_snapshot import enforce_retention
            async with AsyncSessionLocal() as db:
                result = await enforce_retention(db, conv_id)
            stats["conversations_checked"] += 1
            stats["total_pruned"] += result.get("pruned", 0)
        except Exception as exc:
            stats["errors"] += 1
            logger.warning("Global retention: conv=%s failed: %s", conv_id, exc)

    if stats["total_pruned"] > 0:
        logger.info(
            "Global retention: checked %d conversations, pruned %d snapshots",
            stats["conversations_checked"], stats["total_pruned"],
        )
    return stats
