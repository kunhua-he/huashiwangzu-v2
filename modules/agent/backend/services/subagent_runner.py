"""Subagent adapter for the canonical structured action runtime."""
from __future__ import annotations

import json
import logging

from app.database import AsyncSessionLocal

from ..prompt_seeds import SUBAGENT_SYSTEM_KEY
from ..runtime.action_plan import ActionObservation, ActionPlanCheckpoint, ActionPlanItem, ActionState
from ..runtime.action_planner import ActionPlanner
from ..runtime.action_runtime import ActionRuntimeStatus, StructuredActionRuntime
from ..runtime.tool_failure_normalizer import normalize_tool_result_for_model
from ..services.capability_catalog import retrieve_capabilities
from ..services.capability_execution import parse_capability_name
from ..services.runtime_prompt_provider import render_system_prompt

logger = logging.getLogger("v2.agent").getChild("subagent_runner")

SUBAGENT_MAX_ROUNDS = 4


async def _build_system_prompt(
    task_desc: str,
    combined_context: str = "",
    task_write_enabled: bool = False,
    max_rounds: int = SUBAGENT_MAX_ROUNDS,
) -> str:
    context_section = f"参考上下文：\n{combined_context[:2000]}\n\n" if combined_context else ""
    write_guard_section = "" if task_write_enabled else "注意：你只能使用读/检索类工具，不能修改或写入数据。\n"
    async with AsyncSessionLocal() as db:
        return await render_system_prompt(
            db,
            SUBAGENT_SYSTEM_KEY,
            {
                "task_desc": task_desc,
                "context_section": context_section,
                "write_guard_section": write_guard_section,
                "max_rounds": max_rounds,
            },
        )


def _tool_names(tools: list | None) -> set[str] | None:
    if tools is None:
        return None
    return {
        str((item.get("function") or item).get("name") or "")
        for item in tools
        if isinstance(item, dict)
    }


def _filter_catalog(
    catalog: dict,
    *,
    task_write_enabled: bool,
    base_tools: list | None,
    task_tools_param: list | None,
) -> dict:
    allowed = _tool_names(base_tools)
    if task_tools_param:
        requested = {str(item) for item in task_tools_param}
        allowed = requested if allowed is None else allowed & requested

    candidates = []
    for item in catalog.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        name = f"{item.get('module')}__{item.get('action')}"
        contract = item.get("execution_contract") or {}
        if allowed is not None and name not in allowed:
            continue
        if not task_write_enabled and str(contract.get("side_effect_level") or "none") != "none":
            continue
        candidates.append(item)
    return {**catalog, "candidates": candidates}


async def run_single_task(
    task_desc: str,
    task_context: str = "",
    extra_context: str = "",
    base_tools: list | None = None,
    task_tools_param: list | None = None,
    task_write_enabled: bool = False,
    max_rounds: int = SUBAGENT_MAX_ROUNDS,
    caller: str = "",
    caller_role: str = "viewer",
    owner_id: int | None = None,
    retry_prompt: str = "",
    planner: ActionPlanner | None = None,
) -> dict:
    """Execute one subagent task through the same Planner/Executor as chat."""
    resolved_owner_id = owner_id
    if resolved_owner_id is None and caller.startswith("user:"):
        try:
            resolved_owner_id = int(caller.split(":", 1)[1])
        except ValueError:
            resolved_owner_id = None
    if resolved_owner_id is None:
        raise ValueError("owner_id is required for SQL-authorized subagent tools")

    combined = (
        f"{extra_context}\n\n{task_context}"
        if extra_context and task_context
        else (task_context or extra_context or "")
    )
    system_prompt = await _build_system_prompt(
        task_desc,
        combined,
        task_write_enabled,
        max_rounds,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_desc},
    ]
    if retry_prompt:
        messages.append({"role": "user", "content": retry_prompt})

    async def load_catalog() -> dict:
        snapshot = await retrieve_capabilities(
            user_id=resolved_owner_id,
            query=task_desc,
            limit=8,
        )
        return _filter_catalog(
            snapshot,
            task_write_enabled=task_write_enabled,
            base_tools=base_tools,
            task_tools_param=task_tools_param,
        )

    catalog = await load_catalog()
    tool_calls: list[dict] = []
    tool_results: list[dict] = []

    async def execute_action(
        action: ActionPlanItem,
        arguments: dict,
        contract: dict,
    ) -> object:
        from app.services.module_registry import call_capability

        module_key, capability_action = parse_capability_name(action.capability)
        result = await call_capability(
            module_key,
            capability_action,
            arguments,
            caller=caller or f"user:{resolved_owner_id}",
            caller_role=caller_role,
            trusted_user_role=(caller or f"user:{resolved_owner_id}").startswith("user:"),
        )
        normalized, _ = normalize_tool_result_for_model(result, action.capability)
        return normalized

    async def on_plan(checkpoint: ActionPlanCheckpoint) -> None:
        for action in checkpoint.plan.actions:
            if checkpoint.observations.get(action.id) is not None:
                continue
            tool_calls.append({
                "round": checkpoint.planning_round,
                "action_id": action.id,
                "name": action.capability,
                "arguments": action.arguments,
            })

    async def on_observation(
        checkpoint: ActionPlanCheckpoint,
        action: ActionPlanItem,
        observation: ActionObservation,
        result: object | None,
    ) -> None:
        if observation.state not in {
            ActionState.COMPLETED,
            ActionState.FAILED,
            ActionState.BLOCKED,
            ActionState.CANCELLED,
        }:
            return
        tool_results.append({
            "round": checkpoint.planning_round,
            "action_id": action.id,
            "name": action.capability,
            "result": result if result is not None else observation.model_dump(mode="json"),
            "state": observation.state.value,
            "error_class": observation.error_class,
        })

    runtime = StructuredActionRuntime(
        owner_id=resolved_owner_id,
        profile_key="deepseek-v4-flash",
        catalog=catalog,
        execute_action=execute_action,
        max_planning_rounds=max_rounds,
        refresh_catalog=load_catalog,
        on_plan=on_plan,
        on_observation=on_observation,
        planner=planner,
    )
    result = await runtime.run(
        goal=task_desc,
        messages=messages,
    )

    task_error = result.failure_reason or None
    if result.status == ActionRuntimeStatus.NEED_USER_INPUT:
        task_error = "need_user_input"
    conclusion = result.answer.strip()
    if not conclusion and tool_results:
        conclusion = _result_conclusion(tool_results)
    return {
        "task": task_desc,
        "status": (
            "completed"
            if result.status in {ActionRuntimeStatus.DIRECT_ANSWER, ActionRuntimeStatus.COMPLETED}
            else "error"
        ),
        "error": task_error,
        "conclusion": conclusion or "子 Agent 未生成结论",
        "rounds_used": result.planning_rounds,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "need_user_input": result.need_user_input,
    }


def _result_conclusion(tool_results: list[dict]) -> str:
    latest = tool_results[-1].get("result")
    return json.dumps(latest, ensure_ascii=False, default=str)[:4000]
