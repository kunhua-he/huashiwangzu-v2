"""engine编排壳：暴露装配上下文()等给 router。批4：compressor、fallback_chain接入。批5：工具编排、三层记忆、快照、skills注入。
批6：信号总线、分段提示词装配审计、生命周期闭环。"""
import asyncio
import json
import logging
import os
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..services import conversation_service as conv_svc
from .event_store import read_events, project_to_messages, record_event
from .budget_allocator import assemble_context as _budget_assemble_context, estimate_tokens, get_context_budget, DiminishingBudgetTracker
from .layered_memory import record as _layered_memory_record, recall as _layered_memory_recall, fuse as _layered_memory_fuse
from .layered_memory import recall_stable_rules as _recall_stable_rules, recall_chunk as _recall_chunk, three_layer_recall as _three_layer_recall
from .layered_memory import read_static_memory_files as _read_static_memory_files, format_static_memory_for_injection as _format_static_memory
from .experience_memory import match_experience as _experience_match, save_experience as _experience_save, experience_feedback as _experience_feedback, format_injection as _experience_format
from .compressor import compress_middle_with_snapshot as _compress_with_snapshot, hard_truncate_tail as _hard_truncate_tail
from .fallback_chain import chat_with_fallback as _chat_with_fallback, chat_stream_with_fallback as _chat_stream_with_fallback
from .tool_orchestrator import ToolOrchestrator
from .post_turn_hooks import PostTurnHooks
from .skills_loader import find_skills as _find_skills, match_skills as _match_skills, format_skills_for_prompt as _format_skills, resolve_skill_priority as _resolve_skill_priority
from .workflow_strategy import apply_workflow_injection as _apply_workflow_injection
from .signals import get_signal_bus, emit_signal

logger = logging.getLogger("v2.agent").getChild("engine.engine")

# dream 触发节流：每 N 轮对话触发一次
_DREAM_INTERVAL = 5
_COMPRESSION_TOKEN_HEADROOM = 5000


async def assemble_context(
    db: AsyncSession,
    conversation_id: int,
    current_user_input: str,
    profile_key: str,
    owner_id: int,
    agent_code: str = "erp_chat",
) -> tuple[list[dict], dict]:
    # Read agent config for parameter overrides
    agent_cfg = None
    try:
        agent_cfg = await read_agent_config(db, agent_code)
    except Exception as e:
        logger.warning("读取 agent config 失败: %s", e)

    # Resolve effective profile_key: agent config model > caller profile_key > default
    effective_profile_key = profile_key
    if agent_cfg and agent_cfg.get("model"):
        effective_profile_key = agent_cfg["model"]

    try:
        projected = await project_to_messages(db, conversation_id)
        all_events = await read_events(db, conversation_id) if projected else []
    except Exception as e:
        logger.warning("投影事件失败，回退空投影: %s", e)
        projected = []
        all_events = []

    # ── 批6：分段提示词装配 + 注入审计 ─────────────────────────────
    assembly_audit: list[dict] = []
    try:
        system_content = await _build_system_content(db, owner_id, agent_code, assembly_audit=assembly_audit)
    except Exception as e:
        logger.warning("构建系统提示词失败: %s", e)
        system_content = "You are a helpful AI assistant."

    budget = get_context_budget(effective_profile_key)
    projected_tokens = sum(
        max(estimate_tokens([m]), 0) for m in projected[-100:]
    ) if projected else 0
    system_tokens = max(len(system_content) // 2, 0)
    input_tokens = max(len(current_user_input) // 2, 0)
    estimated_total = system_tokens + input_tokens + projected_tokens + 4096

    # ── 信号：预算压力 ─────────────────────────────────────────────
    if budget is not None:
        budget_pressure = min(1.0, estimated_total / budget)
        emit_signal("budget_pressure", budget_pressure, f"est={estimated_total} budget={budget}")

    if budget is not None and estimated_total > budget + _COMPRESSION_TOKEN_HEADROOM and len(all_events) > 30:
        try:
            logger.info("预算超限(est=%d > budget=%d), 触发压缩(含快照)", estimated_total, budget)
            result = await _compress_with_snapshot(db, conversation_id, all_events, projected, effective_profile_key)
            if result.get("status") == "compressed":
                projected = await project_to_messages(db, conversation_id)
                logger.info("压缩后投影完毕, 事件数=%d", len(projected))
        except Exception as e:
            logger.warning("压缩失败（降级到硬截断）: %s", e)
            try:
                await _hard_truncate_tail(db, conversation_id, all_events)
                projected = await project_to_messages(db, conversation_id)
            except Exception as e2:
                logger.warning("硬截断也失败: %s", e2)

    # ── 批6：信号感知的skills注入 ──────────────────────────────────
    signals = get_signal_bus()
    memory_quality = signals.average("memory_recall_quality", n=3, default=0.5)
    try:
        skill_base = os.environ.get("SKILLS_DIR", "data/skills")
        all_skills = _find_skills(skill_base, scope="global")
        workspace_path = os.environ.get("CURRENT_PATH", "")
        if workspace_path:
            workspace_skills_dir = os.path.join(workspace_path, ".agent-skills")
            if os.path.isdir(workspace_skills_dir):
                ws_skills = _find_skills(workspace_skills_dir, scope="workspace")
                all_skills.extend(ws_skills)
        all_skills = _resolve_skill_priority(all_skills)
        matched = _match_skills(all_skills, workspace_path)
        # Signal-aware: reduce skill injection when memory quality is low (less distraction)
        if memory_quality < 0.3:
            matched = [s for s in matched if s.effort >= 3]
            logger.info("Signal: low memory quality (%.2f), limiting skills to high-effort only", memory_quality)
        skill_injection = _format_skills(matched)
        if skill_injection and system_content:
            system_content += "\n\n---\n\n<available_skills>\n" + skill_injection + "\n</available_skills>"
            assembly_audit.append({"segment": "skills", "count": len(matched), "signal_memory_quality": round(memory_quality, 3)})
        else:
            assembly_audit.append({"segment": "skills", "count": 0, "note": "skipped"})
    except Exception as e:
        logger.warning("skills注入失败（non-fatal）: %s", e)
        assembly_audit.append({"segment": "skills", "error": str(e)})

    try:
        messages, diagnosis = _budget_assemble_context(projected, system_content, current_user_input, effective_profile_key)
    except Exception as e:
        logger.warning("预算装配失败，回退原始投影+截尾: %s", e)
        messages = [{"role": "system", "content": system_content}]
        messages.extend(projected[-48:] if len(projected) > 48 else projected)
        diagnosis = {"error": str(e), "fallback": "原始投影截尾"}
    diagnosis["agent_code"] = agent_code
    diagnosis["effective_profile_key"] = effective_profile_key
    diagnosis["assembly_audit"] = assembly_audit

    # ── 三层记忆注入（批5+selector/fencing/snapshot）：稳定规则 + chunk + 语义记忆 ──
    try:
        # Check for frozen snapshot on long-running conversations
        _frozen_key = None
        if agent_cfg and agent_cfg.get("agent_code"):
            # Long tasks reuse snapshot (key set manually by prior turn)
            pass  # snapshot key management is per-task, not automatic yet
        three_layer = await _three_layer_recall(
            owner_id, current_user_input,
            frozen_key=_frozen_key,
        )
        if three_layer.get("injection") and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += "\n\n---\n\n" + three_layer["injection"]
                    break
            selection = three_layer.get("selection", {})
            stable_count = len(three_layer.get("stable_rules", []))
            chunk_count = len(three_layer.get("chunks", []))
            semantic_count = len(three_layer.get("semantic", []))
            dropped_count = selection.get("dropped_count", 0)
            diagnosis["three_layer_memory"] = {
                "stable_rules": stable_count,
                "chunks": chunk_count,
                "semantic": semantic_count,
                "selector_dropped": dropped_count,
                "selection_reason": selection.get("reason", ""),
            }
            assembly_audit.append({
                "segment": "three_layer_memory",
                "stable_rules": stable_count,
                "chunks": chunk_count,
                "semantic": semantic_count,
                "selector_dropped": dropped_count,
            })
            quality_score = three_layer.get("quality_score", 1.0)
            emit_signal("memory_recall_quality", quality_score, f"layer=three_layer sel_drop={dropped_count}")
        else:
            assembly_audit.append({"segment": "three_layer_memory", "injected": False})
    except Exception as e:
        logger.warning("三层记忆注入失败（non-fatal）: %s", e)
        diagnosis["three_layer_memory"] = f"降级: {e}"
        assembly_audit.append({"segment": "three_layer_memory", "error": str(e)})

    # ── 项目工作流约束注入（workflow_strategy） ──
    wf_diag = _apply_workflow_injection(current_user_input, messages)
    diagnosis["workflow_injected"] = wf_diag.get("workflow_injected", False)
    if wf_diag.get("workflow_label"):
        diagnosis["workflow_label"] = wf_diag["workflow_label"]
        assembly_audit.append({"segment": "workflow_strategy", "label": wf_diag["workflow_label"]})

    # ── 成功经验注入（批3） ──
    try:
        matched = await _experience_match(current_user_input, limit=2, caller=f"user:{owner_id}")
        injection = _experience_format(matched)
        if injection and messages:
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += injection
                    break
            diagnosis["experience_injected"] = [e["id"] for e in matched if e.get("id")]
            diagnosis["experience_injection"] = "成功注入" if injection else "无命中"
            assembly_audit.append({"segment": "experience_memory", "count": len(matched)})
        else:
            diagnosis["experience_injection"] = "无命中"
            assembly_audit.append({"segment": "experience_memory", "count": 0})
    except Exception as e:
        logger.warning("经验注入失败（降级，不阻塞）: %s", e)
        diagnosis["experience_injection"] = f"降级: {e}"
        assembly_audit.append({"segment": "experience_memory", "error": str(e)})

    return messages, diagnosis


async def read_agent_config(db: AsyncSession, agent_code: str) -> dict | None:
    """Read agent config from agent_configs table.

    Returns None if no config found for the given agent_code.
    """
    try:
        from ..models import AgentConfig
        r = await db.execute(
            select(AgentConfig).where(AgentConfig.agent_code == agent_code)
        )
        c = r.scalar_one_or_none()
        if not c:
            return None
        return {
            "agent_code": c.agent_code,
            "agent_name": c.agent_name,
            "provider": c.provider,
            "model": c.model,
            "system_prompt": c.system_prompt,
            "enabled": c.enabled,
            "temperature": c.temperature,
            "top_p": c.top_p,
            "max_tokens": c.max_tokens,
            "timeout_ms": c.timeout_ms,
            "fallback_model": c.fallback_model,
            "fallback_enabled": c.fallback_enabled,
            "max_concurrency": c.max_concurrency,
            "cooldown_seconds": c.cooldown_seconds,
            "retry_count": c.retry_count,
            "daily_call_limit": c.daily_call_limit,
            "daily_budget": c.daily_budget,
            "monthly_budget": c.monthly_budget,
            "response_format": c.response_format,
            "log_prompt_enabled": c.log_prompt_enabled,
            "log_response_enabled": c.log_response_enabled,
            "sensitive_action_policy": c.sensitive_action_policy,
            "updated_by": c.updated_by,
        }
    except Exception as e:
        logger.warning("Failed to read agent config for '%s': %s", agent_code, e)
        return None


async def _build_system_content(db: AsyncSession, owner_id: int, agent_code: str = "erp_chat", assembly_audit: list | None = None) -> str:
    """分段装配系统提示词，每段标记来源以供审计回放。

    Audit trail is appended to *assembly_audit* (if provided) as a list of
    ``{"segment": str, "chars": int, ...}`` entries.
    """
    sys_prompt = await conv_svc.get_system_prompt(db)
    ent_prompt = await conv_svc.get_enterprise_prompt(db)
    profile_data = await conv_svc.get_active_user_profile(db, owner_id)
    profile_text = conv_svc._format_profile_text(profile_data)
    layers: list[dict] = []
    audit = assembly_audit if assembly_audit is not None else []

    # Layer 0: Static file memory (zero-latency, deterministic)
    try:
        static_texts = _read_static_memory_files()
        static_injection = _format_static_memory(static_texts)
        if static_injection:
            layers.append({"segment": "static_memory", "content": static_injection})
            audit.append({"segment": "static_memory", "chars": len(static_injection)})
    except Exception as e:
        logger.warning("Static memory read failed (non-fatal): %s", e)
        audit.append({"segment": "static_memory", "error": str(e)})

    if sys_prompt:
        layers.append({"segment": "system_prompt", "content": sys_prompt})
        audit.append({"segment": "system_prompt", "chars": len(sys_prompt)})

    if ent_prompt:
        layers.append({"segment": "enterprise_prompt", "content": ent_prompt})
        audit.append({"segment": "enterprise_prompt", "chars": len(ent_prompt)})

    # Agent config override: custom system_prompt
    try:
        agent_cfg = await read_agent_config(db, agent_code)
        if agent_cfg and agent_cfg.get("system_prompt"):
            content = f"Agent 配置提示词：\n{agent_cfg['system_prompt']}"
            layers.append({"segment": "agent_config_prompt", "content": content})
            audit.append({"segment": "agent_config_prompt", "chars": len(content), "agent_code": agent_code})
    except Exception as e:
        logger.warning("Failed to read agent config prompt: %s", e)
        audit.append({"segment": "agent_config_prompt", "error": str(e)})

    if profile_text:
        layers.append({"segment": "user_profile", "content": profile_text})
        audit.append({"segment": "user_profile", "chars": len(profile_text)})

    result = "\n\n---\n\n".join(l["content"] for l in layers)
    audit.append({"segment": "_total", "chars": len(result), "layer_count": len(layers)})
    return result


# ── 批5：模块级单例 ──────────────────────────────────────────────

_orchestrator: ToolOrchestrator | None = None
_hooks: PostTurnHooks | None = None
_budget_tracker: DiminishingBudgetTracker | None = None


def get_orchestrator(max_concurrency: int = 8) -> ToolOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ToolOrchestrator(max_concurrency=max_concurrency)
    return _orchestrator


def get_budget_tracker() -> DiminishingBudgetTracker:
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = DiminishingBudgetTracker()
    return _budget_tracker


def get_hooks() -> PostTurnHooks:
    global _hooks
    if _hooks is None:
        _hooks = PostTurnHooks()
        # Start the background maintenance loop on first hook access.
        # This ensures the global hooks lifecycle starts with the first
        # real conversation turn rather than at module import time (which
        # may run before the async event loop is ready).
        from .post_turn_hooks import setup_global_hooks
        setup_global_hooks()
    return _hooks


# ── 已实现接口（批2 事实记忆） ──────────────────────────────

async def record_turn(db: AsyncSession, conversation_id: int, owner_id: int, messages: list[dict]) -> dict:
    """批2：从对话消息中提取事实记忆并保存。调用 memory 模块 save 能力。"""
    try:
        # 从对话中提取关键事实（仅 user 和 assistant 消息）
        memory_texts = []
        for msg in messages[-6:]:  # 只看最近几轮
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str) and len(content) > 20:
                memory_texts.append(f"[{role}] {content[:500]}")
        if not memory_texts:
            return {"status": "skipped", "note": "无可提取的记忆内容"}

        combined = "\n\n".join(memory_texts)
        # 用layered_memory客户端保存
        result = await _layered_memory_record(
            text=combined[:2000],
            owner_id=owner_id,
            source="auto-distill",
            conversation_id=conversation_id,
        )
        return result
    except Exception as e:
        logger.warning("记一笔 failed (non-fatal): %s", e)
        return {"status": "fallback", "error": str(e)}


async def compress(db: AsyncSession, conversation_id: int, profile_key: str = "gemma-4") -> dict:
    """批4：事件压缩。调compressor插入 compaction 事件，不删原始事件。"""
    logger.info("压缩 (conv=%s)", conversation_id)
    try:
        all_events = await read_events(db, conversation_id)
        if len(all_events) <= 30:
            return {"status": "skipped", "reason": "事件数不足"}
        result = await _compress_with_snapshot(db, conversation_id, all_events, profile_key=profile_key)
        return result
    except Exception as e:
        logger.warning("compress失败: %s", e)
        try:
            all_events = await read_events(db, conversation_id)
            return await _hard_truncate_tail(db, conversation_id, all_events)
        except Exception as e2:
            return {"status": "error", "error": str(e2)}


async def recall_memory(db: AsyncSession, owner_id: int, query: str) -> list[dict]:
    """批2：语义召回记忆。调用 memory 模块 recall 能力，含顺链扩展。"""
    try:
        results = await _layered_memory_recall(
            owner_id=owner_id,
            query=query,
            limit=5,
            expand_chain=True,
        )
        return results
    except Exception as e:
        logger.warning("召回记忆 failed (non-fatal): %s", e)
        return []


async def fuse_inject(owner_id: int, query: str, memory_ids: list[int], budget_remaining: int) -> str | None:
    """如果预算紧（< MEMORY_FUSE_BUDGET_THRESHOLD），用即时融合压缩多条记忆成简报。

    否则返回 None（直接用总结层概要，省一次调用）。
    """
    if not memory_ids:
        return None
    if budget_remaining is not None and budget_remaining < 2000:
        # 预算紧：融合压缩
        return await _layered_memory_fuse(owner_id, query, memory_ids)
    return None


# 全局 dream 计数器（近似，跨 worker 不精确但够用）
_dream_counter: int = 0


async def trigger_dream(owner_id: int) -> None:
    """每 DREAM_INTERVAL 次调用触发一次 dream（通过 SystemTaskQueue）。"""
    global _dream_counter
    _dream_counter += 1
    if _dream_counter % _DREAM_INTERVAL == 0:
        try:
            from app.database import AsyncSessionLocal
            from app.models.system import SystemTaskQueue
            import json
            async with AsyncSessionLocal() as db:
                task = SystemTaskQueue(
                    task_type="memory_dream",
                    parameters=json.dumps({"owner_id": owner_id}),
                    status="pending",
                    priority=0,
                    module="agent",
                    creator_id=owner_id,
                )
                db.add(task)
                await db.commit()
        except Exception as e:
            logger.warning("dream enqueue failed (non-fatal): %s", e)
            from .failure_diagnostics import record_failure
            await record_failure("engine", "trigger_dream", type(e).__name__, str(e), owner_id=owner_id)


# ── 批4 韧性：fallback_chain聊天（经 gateway service 调用） ─────────────────

async def chat_with_degradation_chain(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
) -> dict:
    """用fallback_chain包装模型调用。主模型失败 → fallback_chain → 本地兜底。"""
    try:
        return await _chat_with_fallback(messages, profile_key, tools, conversation_id=conversation_id)
    except Exception as e:
        logger.error("fallback_chainchat全部失败: %s", e)
        return {"error": str(e), "content": f"(模型调用失败：{e})"}


async def chat_stream_with_degradation_chain(
    messages: list[dict],
    profile_key: str,
    tools: list[dict] | None = None,
    conversation_id: int | None = None,
):
    """流式fallback_chain。首包失败可降级；已经开始流式中途断给清晰错误。"""
    try:
        async for event in _chat_stream_with_fallback(messages, profile_key, tools, conversation_id=conversation_id):
            yield event
    except Exception as e:
        logger.error("fallback_chain流式chat全部失败: %s", e)
        yield {"type": "error", "content": f"(流式模型调用失败：{e})"}
    yield {"type": "done"}


# ── 批3 成功经验：蒸馏 + 结算 ──────────────────────────────

async def distill_experience(
    trigger_condition: str,
    steps: list[dict],
    tools_used: list[str] | None = None,
    source_conversation_id: int | None = None,
    owner_id: int = 0,
) -> None:
    """fire-and-forget：对话成功后，把成功路径蒸馏成一条经验存入经验库。

    降级：失败不影响主对话，但记录到 failure_diagnostics。
    """
    try:
        steps_str = json.dumps(steps, ensure_ascii=False)
        tools_str = json.dumps(tools_used, ensure_ascii=False) if tools_used else None
        await _experience_save(
            trigger_condition=trigger_condition,
            steps=steps_str,
            tools_used=tools_str,
            source_conversation_id=source_conversation_id,
            caller=f"user:{owner_id}" if owner_id else "system:engine",
        )
    except Exception as e:
        logger.warning("蒸馏经验 failed (non-fatal): %s", e)
        from .failure_diagnostics import record_failure
        await record_failure("engine", "distill_experience", type(e).__name__, str(e), conversation_id=source_conversation_id, owner_id=owner_id)


async def settle_experience(
    experience_id: int,
    success: bool,
    note: str | None = None,
    owner_id: int = 0,
) -> None:
    """fire-and-forget：对话结束后，对用过的经验做成功/失败反馈。

    降级：失败不影响主对话，但记录到 failure_diagnostics。
    """
    try:
        await _experience_feedback(
            experience_id=experience_id,
            success=success,
            note=note,
            caller=f"user:{owner_id}" if owner_id else "system:engine",
        )
    except Exception as e:
        logger.warning("经验结算 failed (non-fatal): %s", e)
        from .failure_diagnostics import record_failure
        await record_failure("engine", "settle_experience", type(e).__name__, str(e), owner_id=owner_id)
