"""Workflow recipe service: CRUD, scoring, mining, and injection helpers.

This is the main persistence layer for per-user mined workflow recipes.
Each recipe is a structured description of the shortest known tool chain
for a given user intent, along with scoring and provenance metadata.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentWorkflowRecipe

logger = logging.getLogger("v2.agent").getChild("workflow_recipe")

# ── Scoring constants ──
_RECIPE_DECAY_DAYS = 7          # half-life for recency scoring
_SUCCESS_WEIGHT_SCALE = 20      # max success_weight before lowering boost
_CONFIDENCE_MIN = 0.3            # below this: do not inject
_TOP_N_INJECT = 2                # max recipes to inject per turn


# =====================================================================
# Scoring
# =====================================================================

def _recency_score(last_used_at: datetime | None) -> float:
    """Time-decay factor: 0 (unused) → 1 (just used). Half-life 7 days."""
    if not last_used_at:
        return 0.0
    days = (datetime.now(timezone.utc) - last_used_at).total_seconds() / 86400
    return max(0.1, pow(0.5, days / _RECIPE_DECAY_DAYS))


def compute_confidence(recipe: AgentWorkflowRecipe) -> float:
    """Score a recipe for injection ranking.

    Factors:
      - success_weight (capped)
      - fail_count (penalty)
      - avg_duration (lower = better)
      - avg_tool_count (lower = better)
      - recency
    """
    success = min(recipe.success_weight or 0, _SUCCESS_WEIGHT_SCALE)
    failure_penalty = (recipe.fail_count or 0) * 2.0

    # Speed factor: 1.0 at ≤2s, 0.5 at 10s, 0 at >20s
    dur = recipe.avg_duration_ms or 30000
    speed = max(0.0, 1.0 - (dur / 20000))

    # Tool factor: 1.0 at ≤2 tools, 0.5 at 6 tools
    tools = recipe.avg_tool_count or 5
    tool_eff = max(0.0, 1.0 - ((tools - 1) / 8))

    recency = _recency_score(recipe.last_used_at)
    status_ok = 1.0 if recipe.enabled and recipe.status == "published" else 0.5

    base = max(0.0, success - failure_penalty)
    score = (
        base * 0.35 +
        speed * 0.25 +
        tool_eff * 0.15 +
        recency * 0.15 +
        status_ok * 0.10
    )
    return min(round(score, 4), 10.0)


# =====================================================================
# CRUD
# =====================================================================

async def get_by_owner(
    db: AsyncSession,
    owner_id: int,
    limit: int = 20,
    enabled_only: bool = True,
) -> list[AgentWorkflowRecipe]:
    """List recipes for a user, ordered by confidence desc."""
    stmt = (
        select(AgentWorkflowRecipe)
        .where(AgentWorkflowRecipe.owner_id == owner_id)
        .order_by(desc(AgentWorkflowRecipe.confidence))
        .limit(limit)
    )
    if enabled_only:
        stmt = stmt.where(AgentWorkflowRecipe.enabled)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, recipe_id: int) -> AgentWorkflowRecipe | None:
    result = await db.execute(
        select(AgentWorkflowRecipe).where(AgentWorkflowRecipe.id == recipe_id)
    )
    return result.scalar_one_or_none()


async def upsert_recipe(
    db: AsyncSession,
    owner_id: int,
    name: str,
    intent_label: str,
    trigger_condition: str,
    steps: list[dict],
    tools_used: list[str],
    source_conversation_id: int | None = None,
    source_trajectory_id: int | None = None,
    avg_duration_ms: float | None = None,
    avg_tool_count: float | None = None,
) -> int:
    """Create or update a recipe. If a recipe with same (owner_id, intent_label)
    exists, increment success_weight and update other fields."""
    existing = await db.execute(
        select(AgentWorkflowRecipe)
        .where(AgentWorkflowRecipe.owner_id == owner_id)
        .where(AgentWorkflowRecipe.intent_label == intent_label)
        .limit(1)
    )
    existing_recipe = existing.scalar_one_or_none()

    if existing_recipe:
        existing_recipe.success_weight = (existing_recipe.success_weight or 0) + 1.0
        existing_recipe.fail_count = 0
        existing_recipe.avg_duration_ms = avg_duration_ms
        existing_recipe.avg_tool_count = avg_tool_count
        existing_recipe.last_used_at = datetime.now(timezone.utc)
        existing_recipe.steps = steps
        existing_recipe.tools_used = tools_used
        existing_recipe.trigger_condition = trigger_condition
        existing_recipe.version = (existing_recipe.version or 1) + 1
        existing_recipe.status = "published"
        existing_recipe.confidence = compute_confidence(existing_recipe)
        recipe_id = existing_recipe.id
    else:
        recipe = AgentWorkflowRecipe(
            owner_id=owner_id,
            name=name,
            description="",
            intent_label=intent_label,
            trigger_condition=trigger_condition,
            steps=steps,
            tools_used=tools_used,
            status="published",
            version=1,
            success_weight=1.0,
            fail_count=0,
            avg_duration_ms=avg_duration_ms,
            avg_tool_count=avg_tool_count,
            last_used_at=datetime.now(timezone.utc),
            confidence=0.0,
            source_conversation_id=source_conversation_id,
            source_trajectory_id=source_trajectory_id,
            enabled=True,
        )
        db.add(recipe)
        await db.flush()
        recipe_id = recipe.id
        recipe.confidence = compute_confidence(recipe)

    await db.commit()
    logger.info("Recipe upserted: id=%s owner=%s label=%s", recipe_id, owner_id, intent_label)
    return recipe_id


async def record_failure(db: AsyncSession, recipe_id: int):
    """Increment fail_count and re-compute confidence."""
    recipe = await get_by_id(db, recipe_id)
    if not recipe:
        return
    recipe.fail_count = (recipe.fail_count or 0) + 1
    recipe.confidence = compute_confidence(recipe)
    await db.commit()


async def disable_recipe(db: AsyncSession, recipe_id: int):
    recipe = await get_by_id(db, recipe_id)
    if recipe:
        recipe.enabled = False
        await db.commit()


# =====================================================================
# Match & Inject helpers
# =====================================================================

async def match_recipes(
    db: AsyncSession,
    owner_id: int,
    current_input: str,
    top_n: int = _TOP_N_INJECT,
) -> list[AgentWorkflowRecipe]:
    """Find recipes for this user matching the current input.

    Simple matching: check if any token from current_input appears in
    the recipe intent_label or trigger_condition.
    """
    recipes = await get_by_owner(db, owner_id, limit=50, enabled_only=True)
    if not recipes:
        return []

    tokens = set(current_input.lower().split())
    scored: list[tuple[float, AgentWorkflowRecipe]] = []

    for r in recipes:
        match_score = 0.0
        label_tokens = set(r.intent_label.lower().split())
        trigger_tokens = set(r.trigger_condition.lower().split())
        name_tokens = set(r.name.lower().split())

        overlap = tokens & (label_tokens | trigger_tokens | name_tokens)
        if overlap:
            match_score = len(overlap) / max(len(tokens), 1)

        if match_score > 0:
            combined = match_score * 0.5 + r.confidence * 0.5
            scored.append((combined, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_n]]


def format_recipe_for_injection(recipes: list[AgentWorkflowRecipe]) -> str:
    """Format matched recipes as a compact markdown block for system prompt."""
    if not recipes:
        return ""

    lines: list[str] = ["\n【工作流建议（后台挖掘）】"]
    for r in recipes:
        name = r.name or r.intent_label
        lines.append("")
        lines.append(f"### {name}")
        if r.description:
            lines.append(f"{r.description}")
        if r.steps:
            lines.append("")
            lines.append("推荐步骤：")
            for i, step in enumerate(r.steps, 1):
                if isinstance(step, dict):
                    step_text = step.get("step") or step.get("action") or json.dumps(step, ensure_ascii=False)
                else:
                    step_text = str(step)
                lines.append(f"{i}. {step_text}")
        if r.tools_used:
            lines.append("")
            lines.append(f"使用工具：{' → '.join(str(t) for t in r.tools_used)}")
        lines.append(f"（成功率 {r.success_weight or 0:.0f} 次 · 平均耗时 {r.avg_duration_ms / 1000:.1f}s · 置信度 {r.confidence:.2f}）")

    return "\n".join(lines)


# =====================================================================
# Mining helpers
# =====================================================================

async def run_mining_job(
    db: AsyncSession,
    owner_id: int,
    **kwargs,
) -> dict[str, Any]:
    """Mine workflow recipes from recent successful trajectories.

    This is a placeholder rule-based miner. It scans recent trajectory
    records and identifies high-success, low-tool-count paths.
    """
    from ..models import AgentTrajectoryRecord

    result = await db.execute(
        select(AgentTrajectoryRecord)
        .where(AgentTrajectoryRecord.owner_id == owner_id)
        .where(not AgentTrajectoryRecord.error_occurred)
        .order_by(desc(AgentTrajectoryRecord.id))
        .limit(100)
    )
    trajectories = list(result.scalars().all())
    if not trajectories:
        return {"mined": 0, "reason": "no_successful_trajectories"}

    # Group by intent-label heuristics (first ~60 chars of user_input)
    groups: dict[str, list[AgentTrajectoryRecord]] = {}
    for t in trajectories:
        intent = t.user_input[:60]
        if intent not in groups:
            groups[intent] = []
        groups[intent].append(t)

    mined = 0
    for intent, trajs in groups.items():
        if len(trajs) < 2:
            continue  # need at least 2 successes to mine

        sum(1 for t in trajs if not t.error_occurred)
        sum(1 for t in trajs if t.error_occurred)
        avg_dur = sum((t.duration_ms or 0) for t in trajs) / len(trajs) if trajs else None

        # Extract tool names from tool_calls
        all_tools: list[str] = []
        all_steps: list[dict] = []
        for t in trajs:
            if t.tool_calls:
                for tc in t.tool_calls[:]:
                    if isinstance(tc, dict):
                        name = tc.get("name") or tc.get("function", {}).get("name", "")
                        if name:
                            all_tools.append(name)
                        step = {"step": name, "arguments": tc.get("arguments", {}),
                                "tool_call_id": tc.get("tool_call_id")}
                        all_steps.append(step)

        avg_tool_count = len(all_tools) / len(trajs) if trajs else None

        if all_tools:
            await upsert_recipe(
                db,
                owner_id=owner_id,
                name=intent,
                intent_label=intent,
                trigger_condition=intent,
                steps=all_steps[:10],
                tools_used=list(dict.fromkeys(all_tools))[:10],
                source_conversation_id=trajs[-1].conversation_id,
                source_trajectory_id=trajs[-1].id,
                avg_duration_ms=avg_dur,
                avg_tool_count=avg_tool_count,
            )
            mined += 1

    return {"mined": mined, "processed": len(groups)}
