"""RuntimeTaskSink — unified persistence and post-turn hook gateway.

Consolidates assistant message persistence, event flushing, timeline
storage, and hook triggering — all the scatter-shot DB work that used
to live at the bottom of ``event_stream()`` in ``chat.py``.

Also projects validated ``ResourceRef`` values into message metadata,
completion evidence, experience patterns, and Agent asset entries.
"""

from __future__ import annotations

import json
import logging
import re

from app.database import AsyncSessionLocal
from app.schemas.platform_resource import ResourceRef, ResourceType
from app.services.module_registry import call_capability
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine.event_store import record_event as _record_event
from ..engine.failure_diagnostics import record_failure as _record_failure
from ..engine.path_trace import build_path_trace_summary
from ..runtime.content_gate import (
    final_clean_content,
)
from ..services import conversation_service as conv_svc
from .action_plan import ActionPlanCheckpoint, ActionState
from .workflow_link import WorkflowRuntimeLink

logger = logging.getLogger("v2.agent").getChild("runtime.task_sink")

_EXPERIENCE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/)[^\s\"']+")
_EXPERIENCE_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_EXPERIENCE_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_EXPERIENCE_RESOURCE_ID_RE = re.compile(
    r"\b(?:file|document|resource|record|task|artifact|chunk|owner|user)_id\s*[:=#]?\s*[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
_EXPERIENCE_FILE_RE = re.compile(
    r"\b[^\s/\\]+\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|png|jpe?g|webp)\b",
    re.IGNORECASE,
)
_EXPERIENCE_LONG_NUMBER_RE = re.compile(r"\b\d{4,}\b")


def resource_refs_from_checkpoint(
    checkpoint: ActionPlanCheckpoint | None,
) -> list[ResourceRef]:
    """Return validated references in deterministic plan order."""
    if checkpoint is None:
        return []
    references: list[ResourceRef] = []
    seen: set[tuple[str, str, str]] = set()
    for action in checkpoint.plan.actions:
        observation = checkpoint.observations.get(action.id)
        if observation is None or observation.state != ActionState.COMPLETED:
            continue
        for reference in observation.references:
            key = (reference.type.value, str(reference.id), reference.locator)
            if key in seen:
                continue
            seen.add(key)
            references.append(reference)
    return references


def _resource_ref_payloads(references: list[ResourceRef]) -> list[dict]:
    return [
        reference.model_dump(mode="json", by_alias=True)
        for reference in references
    ]


def _sanitized_goal_signature(goal: str, capability_path: str) -> str:
    value = _EXPERIENCE_PATH_RE.sub("<path>", str(goal or ""))
    value = _EXPERIENCE_URL_RE.sub("<url>", value)
    value = _EXPERIENCE_EMAIL_RE.sub("<email>", value)
    value = _EXPERIENCE_RESOURCE_ID_RE.sub("<resource_id>", value)
    value = _EXPERIENCE_FILE_RE.sub("<file>", value)
    value = _EXPERIENCE_LONG_NUMBER_RE.sub("<number>", value)
    value = " ".join(value.split())[:700]
    if not value:
        value = "Completed reusable action plan"
    return f"{value}; capability path: {capability_path}"[:1000]


def _coerce_json_like(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def extract_query_context_ids(value: object, *, limit: int = 8) -> list[int]:
    """Extract persisted knowledge query_context_id values from tool payloads."""
    found: list[int] = []
    seen: set[int] = set()

    def _walk(node: object, depth: int = 0) -> None:
        if len(found) >= limit or depth > 10:
            return
        node = _coerce_json_like(node)
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "query_context_id":
                    try:
                        context_id = int(child)
                    except (TypeError, ValueError):
                        context_id = 0
                    if context_id > 0 and context_id not in seen:
                        seen.add(context_id)
                        found.append(context_id)
                        if len(found) >= limit:
                            return
                _walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                _walk(child, depth + 1)
                if len(found) >= limit:
                    return

    _walk(value)
    return found


def build_retrieval_reflection_excerpt(
    *,
    user_input: str,
    assistant_text: str,
    messages: list[dict],
    max_chars: int = 6000,
) -> str:
    """Build a compact turn excerpt for retrieval feedback reflection."""
    parts = []
    user_input = str(user_input or "").strip()
    assistant_text = str(assistant_text or "").strip()
    if user_input:
        parts.append(f"用户本轮问题:\n{user_input[:1800]}")
    if assistant_text:
        parts.append(f"助手本轮回答:\n{assistant_text[:3600]}")

    if not parts:
        recent = []
        for message in messages[-4:]:
            role = str(message.get("role") or "unknown")
            content = str(message.get("content") or "").strip()
            if content:
                recent.append(f"{role}: {content[:1200]}")
        if recent:
            parts.append("最近对话:\n" + "\n\n".join(recent))

    return "\n\n".join(parts)[:max_chars]


class RuntimeTaskSink:
    """One-stop persistence gateway for a single conversation turn.

    Usage::

        sink = RuntimeTaskSink(conversation_id, owner_id)
        await sink.persist_assistant(...)
        await sink.persist_pending_events(...)
        await sink.run_post_turn_hooks(...)
    """

    def __init__(
        self,
        conversation_id: int,
        owner_id: int,
        profile_key: str = "deepseek-v4-flash",
        user_input: str = "",
        intent_preflight: dict | None = None,
        route_diagnostics: dict | None = None,
        workflow_link: WorkflowRuntimeLink | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.owner_id = owner_id
        self.profile_key = profile_key
        self.user_input = user_input
        self.intent_preflight = intent_preflight or {}
        self.route_diagnostics = route_diagnostics or {}
        self.workflow_link = workflow_link

    @property
    def workflow_run_id(self) -> int | None:
        return self.workflow_link.run_id if self.workflow_link else None

    @property
    def workflow_step_id(self) -> int | None:
        return self.workflow_link.step_id if self.workflow_link else None

    @property
    def agent_run_id(self) -> str | None:
        return self.workflow_link.agent_run_id if self.workflow_link else None

    async def ensure_workflow_started(self, db: AsyncSession, *, reason: str = "runtime") -> None:
        if self.workflow_link:
            await self.workflow_link.ensure_started(db, reason=reason)

    async def workflow_record_tool_started(self, db: AsyncSession, tool: dict) -> int | None:
        if not self.workflow_link:
            return None
        try:
            return await self.workflow_link.record_tool_started(db, tool)
        except Exception as exc:
            logger.warning("workflow record tool start failed (non-fatal): %s", exc)
            return None

    async def workflow_mark_invalid_tool(self, db: AsyncSession, tool: dict, message: str) -> None:
        if not self.workflow_link:
            return
        try:
            await self.workflow_link.mark_invalid_tool(db, tool, message)
        except Exception as exc:
            logger.warning("workflow invalid-tool record failed (non-fatal): %s", exc)

    async def workflow_mark_tool_result(self, db: AsyncSession, result_event: dict) -> None:
        if not self.workflow_link:
            return
        try:
            await self.workflow_link.mark_tool_result(db, result_event)
        except Exception as exc:
            logger.warning("workflow tool result record failed (non-fatal): %s", exc)

    async def workflow_complete_turn(
        self,
        db: AsyncSession,
        *,
        message_id: int | None,
        tool_events: list[dict],
        completion_evidence: list[dict] | None = None,
        usage: dict | None = None,
    ) -> None:
        if not self.workflow_link:
            return
        try:
            await self.workflow_link.record_turn_completion(
                db,
                message_id=message_id,
                tool_events=tool_events,
                completion_evidence=completion_evidence,
                usage=usage,
            )
        except Exception as exc:
            logger.warning("workflow turn completion failed (non-fatal): %s", exc)

    async def workflow_record_runtime_failure(
        self,
        db: AsyncSession,
        *,
        error_type: str,
        error_message: str,
    ) -> None:
        if not self.workflow_link:
            return
        try:
            await self.workflow_link.record_runtime_failure(
                db,
                error_type=error_type,
                error_message=error_message,
            )
        except Exception as exc:
            logger.warning("workflow runtime failure record failed (non-fatal): %s", exc)

    @staticmethod
    def check_tool_success(tool_events: list[dict]) -> bool:
        """Unified tool result success checker.

        Returns ``True`` only if every tool call that produced a result
        completed without errors. Checks in order:
        1. Event-level ``event_type == "error"`` ⇒ fail.
        2. Tool result inner ``success`` field (``true`` / ``false``).
        3. Tool result top-level ``error`` key (non-empty ⇒ fail).
        4. Unified envelope ``{"success": false, ...}``.
        5. Policy / approval denial (``denied``, ``policy_blocked``).
        6. Exception or cancellation markers.

        **All** consumers (trajectory, workflow gate, completion evidence)
        **must** go through this function — no hardcoded ``error_occurred``.
        """
        has_error_event = any(
            e.get("event_type") == "error" for e in tool_events
        )
        if has_error_event:
            return False

        for ev in tool_events:
            if ev.get("type") != "tool_result":
                continue
            result = ev.get("result", {})
            if isinstance(result, dict):
                if not result.get("success", True):
                    return False
                if result.get("error"):
                    return False
                inner = result.get("data", result)
                if isinstance(inner, dict):
                    if inner.get("success") is False:
                        return False
                    if inner.get("error"):
                        return False
                if result.get("denied") or result.get("policy_blocked"):
                    return False
        return True

    @staticmethod
    def _is_tool_result_error(result: dict) -> bool:
        """Check a single tool result dict for any error signal."""
        if not isinstance(result, dict):
            return True
        if not result.get("success", True):
            return True
        if result.get("error"):
            return True
        if result.get("denied") or result.get("policy_blocked"):
            return True
        inner = result.get("data", result)
        if isinstance(inner, dict):
            if inner.get("success") is False:
                return True
            if inner.get("error"):
                return True
        return False

    async def persist_assistant(
        self,
        db: AsyncSession,
        full_content: str,
        thinking_parts: list[str],
        tool_events: list[dict],
        timeline: list[dict],
        usage: dict | None = None,
        resource_refs: list[ResourceRef] | None = None,
    ) -> int | None:
        """Save the assistant message, meta, and return the message id."""
        if not full_content:
            return None

        clean_content = final_clean_content("".join(full_content))
        if not clean_content:
            logger.warning(
                "persist_assistant skipped — content cleared to empty by final_clean_content "
                "(conv=%d)", self.conversation_id,
            )
            return None
        msg = await conv_svc.add_message(
            db, self.owner_id, self.conversation_id,
            "assistant", clean_content,
        )
        safe_events = json.loads(json.dumps(tool_events, default=str))
        safe_timeline = json.loads(json.dumps(timeline, default=str))
        await conv_svc.add_message_meta(
            db,
            owner_id=self.owner_id,
            conversation_id=self.conversation_id,
            message_id=msg.id,
            thinking="\n".join(thinking_parts) if thinking_parts else "",
            references=_resource_ref_payloads(resource_refs or []),
            tool_events=safe_events,
            timeline=safe_timeline,
            usage=usage,
        )
        logger.info(
            "[DIAG] persist_assistant DONE msg=%d timeline_len=%d full_len=%d usage=%s",
            msg.id, len(timeline), len(full_content),
            json.dumps(usage) if usage else "None",
        )
        try:
            await _record_event(
                db,
                self.conversation_id,
                "path_trace_summary",
                build_path_trace_summary(
                    user_input=self.user_input,
                    assistant_text=clean_content,
                    intent_preflight=self.intent_preflight,
                    route_diagnostics=self.route_diagnostics,
                    tool_events=safe_events,
                    timeline=safe_timeline,
                    usage=usage,
                    message_id=msg.id,
                    sync_success_path_save_possible=False,
                ),
                llm_response_id=None,
            )
        except Exception as exc:
            logger.warning("path trace summary record failed (non-fatal): %s", exc)
        return msg.id

    async def persist_pending_events(
        self,
        db: AsyncSession,
        pending_events: list[dict],
        persisted_count: int = 0,
    ) -> int:
        """Flush unpersisted events from *pending_events*.

        Returns the count of events that were successfully persisted
        (``persisted_count + new_count``), so failed events are retried
        on the next incremental persist rather than silently lost.
        """
        new_count = 0
        for pe in pending_events[persisted_count:]:
            try:
                await _record_event(
                    db, self.conversation_id,
                    pe["event_type"], pe["payload"],
                    pe.get("llm_response_id"),
                )
                new_count += 1
            except Exception as exc:
                logger.warning(
                    "persist_pending_events record_event failed (non-fatal): %s", exc,
                )
                break
        logger.info(
            "[DIAG] persist_pending_events done (new=%d total=%d)",
            new_count, len(pending_events),
        )
        return persisted_count + new_count

    async def run_post_turn_hooks(
        self,
        db: AsyncSession,
        messages: list[dict],
        tool_events: list[dict],
        timeline: list[dict],
        trajectory_id: int | None = None,
        turn_index: int | None = None,
    ) -> None:
        """Run post-turn hooks via durable SystemTaskQueue.

        Cheap hooks (context_snapshot, prompt_suggestion, cleanup_archive)
        run inline. Expensive/async hooks (memory_distill, profile_evolve,
        experience learning) are submitted to SystemTaskQueue for durable
        cross-worker execution.
        """
        try:
            from ..engine.event_store import record_event as _record_event
            from ..engine.post_turn_hooks import _get_turn_count

            # ── Cheap hooks: inline ────────────────────────────────
            turn_count = await _get_turn_count(db, self.conversation_id)

            # context_snapshot (every N turns)
            if turn_count > 0 and turn_count % 3 == 0:
                try:
                    from ..engine.context_snapshot import take_snapshot
                    from ..engine.event_store import read_events
                    events = await read_events(db, self.conversation_id)
                    await take_snapshot(
                        db=db, conversation_id=self.conversation_id,
                        snapshot_type="periodic",
                        messages=messages, events=events,
                        summary=f"Periodic snapshot at turn {turn_count}",
                    )
                except Exception as exc:
                    logger.warning("context_snapshot failed (non-fatal): %s", exc)

            # prompt_suggestion (inline, cheap)
            assistant_text = ""
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    assistant_text = str(msg.get("content", "") or "").strip()
                    break
            if assistant_text and len(assistant_text) < 120:
                try:
                    await _record_event(
                        db, self.conversation_id,
                        "hook_prompt_suggestion",
                        {"owner_id": self.owner_id, "assistant_length": len(assistant_text),
                         "suggestion": "assistant_reply_too_short"},
                        llm_response_id=None,
                    )
                except Exception as exc:
                    logger.warning("prompt_suggestion failed (non-fatal): %s", exc)

            # cleanup_archive (inline, cheap)
            if turn_count > 0 and turn_count % 3 == 0:
                try:
                    from sqlalchemy import delete, desc, select

                    from ..models import ContextSnapshot
                    r = await db.execute(
                        select(ContextSnapshot.id)
                        .where(ContextSnapshot.conversation_id == self.conversation_id,
                               ContextSnapshot.snapshot_type == "periodic")
                        .order_by(desc(ContextSnapshot.id)).offset(10)
                    )
                    stale_ids = [row[0] for row in r.all()]
                    if stale_ids:
                        await db.execute(
                            delete(ContextSnapshot).where(ContextSnapshot.id.in_(stale_ids))
                        )
                        await db.commit()
                except Exception as exc:
                    logger.warning("cleanup_archive failed (non-fatal): %s", exc)

            # ── Expensive hooks: SystemTaskQueue ──────────────────
            await self.submit_background_task(
                "memory_distill",
                {"conversation_id": self.conversation_id, "owner_id": self.owner_id,
                 "user_content": self.user_input,
                 "assistant_content": assistant_text,
                 "trajectory_id": trajectory_id, "turn_index": turn_index},
            )

            await self.submit_background_task(
                "profile_evolve",
                {"conversation_id": self.conversation_id, "owner_id": self.owner_id,
                 "trajectory_id": trajectory_id, "turn_index": turn_index},
            )

            query_context_ids = extract_query_context_ids(tool_events)
            if query_context_ids:
                await self.submit_background_task(
                    "knowledge_retrieval_reflect",
                    {
                        "owner_id": self.owner_id,
                        "conversation_id": self.conversation_id,
                        "query_context_ids": query_context_ids,
                        "conversation_excerpt": build_retrieval_reflection_excerpt(
                            user_input=self.user_input,
                            assistant_text=assistant_text,
                            messages=messages,
                        ),
                        "trajectory_id": trajectory_id,
                        "turn_index": turn_index,
                    },
                )

            await self._enqueue_context_compact()

            logger.info("Post-turn hooks submitted via SystemTaskQueue for conv=%d", self.conversation_id)
        except Exception as exc:
            logger.warning(
                "post-turn hooks enqueue failed (non-fatal): %s", exc,
            )

    async def _enqueue_context_compact(self) -> None:
        """Enqueue async context compaction after reply persistence.

        Reads the latest event watermark and submits a durable task.
        Idempotency is handled by the unique constraint on
        (conversation_id, until_event_id, generation) in the handler.
        """
        try:
            from sqlalchemy import func, select

            from ..models import AgentEvent
            async with AsyncSessionLocal() as _s:
                r = await _s.execute(
                    select(func.max(AgentEvent.id)).where(
                        AgentEvent.conversation_id == self.conversation_id,
                    )
                )
                until_event_id = r.scalar_one_or_none()
            if not until_event_id:
                logger.debug("No events to compact for conv=%d", self.conversation_id)
                return
            await self.submit_background_task(
                "agent_context_compact",
                {
                    "conversation_id": self.conversation_id,
                    "owner_id": self.owner_id,
                    "until_event_id": int(until_event_id),
                    "profile_key": self.profile_key,
                },
            )
        except Exception as exc:
            logger.warning("context_compact enqueue failed (non-fatal): %s", exc)

    async def record_trajectory(
        self,
        db: AsyncSession,
        turn_index: int,
        tool_calls: list[dict],
        tool_results: list[dict],
        assistant_response: str,
        thinking_level: str | None = None,
        error_occurred: bool = False,
        duration_ms: float | None = None,
        token_count: int | None = None,
    ) -> dict:
        """Record turn trajectory (idempotent upsert by conv+turn)."""
        from ..services.trajectory_service import record_turn as _record_turn
        return await _record_turn(
            db,
            conversation_id=self.conversation_id,
            owner_id=self.owner_id,
            session_id=f"conv_{self.conversation_id}",
            turn_index=turn_index,
            user_input=self.user_input,
            tool_calls=tool_calls,
            tool_results=tool_results,
            assistant_response=assistant_response,
            thinking_level=thinking_level,
            error_occurred=error_occurred,
            duration_ms=duration_ms,
            token_count=token_count,
        )

    async def generate_completion_evidence(
        self,
        checkpoint: ActionPlanCheckpoint | None,
    ) -> list[dict]:
        """Project validator-backed action observations into completion evidence."""
        if checkpoint is None:
            return []
        evidence: list[dict] = []
        for action in checkpoint.plan.actions:
            observation = checkpoint.observations.get(action.id)
            if observation is None:
                evidence.append({
                    "action_id": action.id,
                    "capability": action.capability,
                    "state": ActionState.PENDING.value,
                    "completion_check": action.completion_check,
                    "contract_verified": False,
                    "resource_refs": [],
                    "error_class": "missing_observation",
                })
                continue
            evidence.append({
                "action_id": action.id,
                "capability_id": action.capability_id,
                "capability": action.capability,
                "state": observation.state.value,
                "completion_check": action.completion_check,
                "contract_verified": observation.state == ActionState.COMPLETED,
                "resource_refs": _resource_ref_payloads(observation.references),
                "error_class": observation.error_class,
            })
        return evidence

    async def submit_completed_experience(
        self,
        checkpoint: ActionPlanCheckpoint | None,
    ) -> dict:
        """Submit a sanitized action pattern after the full DAG has completed."""
        if checkpoint is None or self.owner_id <= 0:
            return {"submitted": False, "reason": "missing_checkpoint_or_owner"}
        if checkpoint.experience_submitted:
            return {
                "submitted": False,
                "reason": "already_submitted",
                "experience_id": checkpoint.experience_id,
            }
        if any(
            checkpoint.observations.get(action.id) is None
            or checkpoint.observations[action.id].state != ActionState.COMPLETED
            for action in checkpoint.plan.actions
        ):
            return {"submitted": False, "reason": "plan_not_completed"}

        action_pattern = [
            {
                "id": action.id,
                "capability": action.capability,
                "depends_on": list(action.depends_on),
                "expected_references": [item.value for item in action.expected_references],
            }
            for action in checkpoint.plan.actions
        ]
        reference_types = sorted({
            reference.type.value
            for reference in resource_refs_from_checkpoint(checkpoint)
        })
        capability_path = " -> ".join(action.capability for action in checkpoint.plan.actions)
        payload = {
            "goal_signature": _sanitized_goal_signature(checkpoint.plan.goal, capability_path),
            "action_pattern": action_pattern,
            "source_conversation_id": self.conversation_id if self.conversation_id > 0 else None,
            "scope_type": "user",
            "preconditions": {
                "action_count": len(action_pattern),
                "dependency_edge_count": sum(len(action.depends_on) for action in checkpoint.plan.actions),
            },
            "completion_evidence": {
                "all_actions_completed": True,
                "completed_action_count": len(action_pattern),
                "reference_types": reference_types,
            },
        }
        try:
            result = await call_capability(
                "memory",
                "save_experience",
                payload,
                caller=f"user:{self.owner_id}",
                caller_role="viewer",
                actor="system:agent-engine",
            )
        except Exception as exc:
            logger.warning("structured experience save failed (non-fatal): %s", exc)
            return {"submitted": False, "reason": str(exc)}
        if not isinstance(result, dict) or result.get("success") is False:
            return {"submitted": False, "reason": "capability_failed", "result": result}
        result_data = result.get("data", result)
        checkpoint.experience_submitted = True
        if isinstance(result_data, dict):
            try:
                checkpoint.experience_id = int(result_data.get("id") or 0) or None
            except (TypeError, ValueError):
                checkpoint.experience_id = None
        return {"submitted": True, "result": result_data}

    async def submit_background_task(
        self,
        task_type: str,
        parameters: dict,
    ) -> int | None:
        """Submit a durable background task to SystemTaskQueue.

        Returns the task ID, or None on failure.
        """
        try:
            from app.database import AsyncSessionLocal as _AsyncSessionLocal
            from app.services.task_dispatcher import publish_task
            async with _AsyncSessionLocal() as _s:
                task = await publish_task(
                    _s,
                    task_type=task_type,
                    module="agent",
                    owner_id=self.owner_id,
                    body=parameters,
                    requested_by=f"user:{self.owner_id}",
                    trigger="agent.runtime.task_sink",
                    priority=0,
                )
                await _s.commit()
                await _s.refresh(task)
                logger.info("Background task submitted: type=%s conv=%d task_id=%s", task_type, self.conversation_id, task.id)
                return task.id
        except Exception as exc:
            logger.warning("Failed to submit background task %s: %s", task_type, exc)
            return None

    async def record_event(
        self,
        db: AsyncSession,
        event_type: str,
        payload: dict,
        llm_response_id: str | None = None,
    ) -> None:
        """Record a single event via event_store."""
        try:
            await _record_event(
                db, self.conversation_id, event_type, payload,
                llm_response_id=llm_response_id,
            )
        except Exception as exc:
            logger.warning(
                "record_event(%s) failed (non-fatal): %s", event_type, exc,
            )

    async def record_assets(
        self,
        resource_refs: list[ResourceRef],
        skip_file_ids: set[int] | None = None,
    ) -> list[int]:
        """Create Agent assets for canonical file references only."""
        if not resource_refs:
            return []
        asset_ids: list[int] = []
        try:
            from app.services.asset_service import create_asset

            async with AsyncSessionLocal() as _ad:
                for reference in resource_refs:
                    if reference.type != ResourceType.file:
                        continue
                    try:
                        file_id = int(reference.id)
                    except (TypeError, ValueError):
                        logger.warning("Asset create skipped for non-numeric file ResourceRef id=%r", reference.id)
                        continue
                    if skip_file_ids and file_id in skip_file_ids:
                        continue
                    provenance = reference.provenance or {}
                    capability = str(provenance.get("capability") or "")
                    action_id = str(provenance.get("action_id") or "")
                    try:
                        asset = await create_asset(
                            _ad,
                            file_id=file_id,
                            owner_id=self.owner_id,
                            asset_type="generated",
                            conversation_id=self.conversation_id,
                            tool_name=capability,
                            tool_call_id=action_id,
                        )
                        asset_ids.append(asset.id)
                        logger.info(
                            "Asset auto-created: id=%d file_id=%d tool=%s conv=%d",
                            asset.id, file_id, capability,
                            self.conversation_id,
                        )
                    except Exception as _ae:
                        logger.warning(
                            "Asset create skipped for file_id=%d tool=%s (non-fatal): %s",
                            file_id, capability, _ae,
                        )
        except Exception as exc:
            logger.warning(
                "record_assets failed (non-fatal): %s", exc,
            )
        return asset_ids

    async def record_failure(
        self,
        source: str,
        operation: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """Record a failure diagnostic."""
        try:
            await _record_failure(
                source, operation, error_type, error_message,
                conversation_id=self.conversation_id,
                owner_id=self.owner_id,
            )
        except Exception as exc:
            logger.warning(
                "record_failure failed (non-fatal): %s", exc,
            )
