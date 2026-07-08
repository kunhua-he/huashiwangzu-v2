from datetime import datetime, timezone

from ..models import AgentWorkflowRecipe
from .workflow_recipe_service import recipe_match_score


def _recipe(intent: str, tools: list[str] | None = None, confidence: float = 0.8):
    return AgentWorkflowRecipe(
        owner_id=1,
        name=intent,
        intent_label=intent,
        trigger_condition=intent,
        steps=[{"step": "skill_use"}],
        tools_used=tools or ["desktop-tools__list_files"],
        status="published",
        success_weight=5,
        fail_count=0,
        avg_duration_ms=2500,
        avg_tool_count=2,
        last_used_at=datetime.now(timezone.utc),
        confidence=confidence,
        enabled=True,
    )


def test_similar_text_matches_same_recipe():
    recipe = _recipe("查看资料文件")

    assert recipe_match_score("查看资料文件", recipe) > 0.7
    assert recipe_match_score("资料文件查看", recipe) > 0.2


def test_recipe_tool_names_can_contribute_to_match():
    recipe = _recipe("生成摘要表", ["generic-report__create_summary_table"])

    assert recipe_match_score("生成摘要表", recipe) > 0.7
    assert recipe_match_score("create_summary_table", recipe) > 0.2


def test_unrelated_query_scores_low():
    recipe = _recipe("查看资料文件")

    assert recipe_match_score("今天销售额怎么样", recipe) < 0.25
    assert recipe_match_score("分析加盟方案价格", recipe) < 0.25
