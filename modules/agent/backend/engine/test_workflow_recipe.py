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


def test_desktop_file_paraphrases_match_same_recipe():
    recipe = _recipe("查看桌面文件")

    assert recipe_match_score("我桌面有什么文件？", recipe) > 0.2
    assert recipe_match_score("帮我打开桌面的文件", recipe) > 0.2
    assert recipe_match_score("看一下桌面里的 xlsx", recipe) > 0.2
    assert recipe_match_score("桌面上那个 word 文档打开看看", recipe) > 0.2


def test_excel_generation_paraphrases_match_excel_recipe():
    recipe = _recipe("生成 Excel 摘要表格", ["office-gen__xlsx", "desktop-tools__replace_file"])

    assert recipe_match_score("把总结输出成 excel", recipe) > 0.2
    assert recipe_match_score("帮我生成 xlsx 表格", recipe) > 0.2
    assert recipe_match_score("导出一份摘要表", recipe) > 0.2
    assert recipe_match_score("重新覆盖旧的表格文件", recipe) > 0.2


def test_unrelated_query_scores_low():
    recipe = _recipe("查看桌面文件")

    assert recipe_match_score("今天销售额怎么样", recipe) < 0.25
    assert recipe_match_score("分析加盟方案价格", recipe) < 0.25
