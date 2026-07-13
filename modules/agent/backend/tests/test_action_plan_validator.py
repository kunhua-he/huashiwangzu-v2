from __future__ import annotations

import pytest

from modules.agent.backend.runtime.action_plan import (
    ActionObservation,
    ActionPlan,
    ActionPlanItem,
    ActionState,
    ResourceRef,
)
from modules.agent.backend.runtime.action_plan_validator import (
    ActionPlanValidationError,
    ActionPlanValidator,
)


def _catalog() -> dict:
    return {
        "catalog_hash": "a" * 64,
        "principal": {"profile_version": "b" * 20},
        "candidates": [{
            "capability_id": 7,
            "module": "knowledge",
            "action": "search",
            "parameters": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "execution_contract": {"input_schema": {}},
        }],
    }


def _plan(arguments: dict) -> ActionPlan:
    return ActionPlan(
        goal="搜索知识库",
        catalog_hash="a" * 64,
        principal_version="b" * 20,
        actions=[ActionPlanItem(
            id="a1",
            capability_id=7,
            capability="knowledge__search",
            arguments=arguments,
            completion_check="返回检索结果",
        )],
        final_completion_check="用户获得结果",
    )


def test_validator_accepts_authorized_schema_valid_plan() -> None:
    validator = ActionPlanValidator(user_id=4, catalog=_catalog())
    assert validator.validate_plan(_plan({"query": "产品手册", "top_k": 5}))


def test_validator_normalizes_legacy_parameter_schema_aliases() -> None:
    catalog = _catalog()
    catalog["candidates"][0]["parameters"] = {
        "query": {"type": "string"},
        "top_k": {"type": "int"},
        "refine": {"type": "bool"},
    }
    validator = ActionPlanValidator(user_id=4, catalog=catalog)
    assert validator.validate_plan(_plan({"query": "产品手册", "top_k": 5, "refine": True}))


def test_validator_rejects_invalid_argument_type() -> None:
    validator = ActionPlanValidator(user_id=4, catalog=_catalog())
    with pytest.raises(ActionPlanValidationError) as exc_info:
        validator.validate_plan(_plan({"query": "产品手册", "top_k": "five"}))
    assert exc_info.value.issues[0].code == "invalid_arguments"


def test_reference_binding_requires_completed_dependency() -> None:
    validator = ActionPlanValidator(user_id=4, catalog=_catalog())
    action = ActionPlanItem(
        id="a2",
        capability_id=7,
        capability="knowledge__search",
        arguments={"query": "${a1.references[0].id}"},
        depends_on=["a1"],
        completion_check="查询引用",
    )
    observations = {
        "a1": ActionObservation(
            action_id="a1",
            state=ActionState.COMPLETED,
            references=[ResourceRef(type="file", id=99)],
        ),
    }
    assert validator.bind_arguments(action, observations) == {"query": 99}


def test_plan_validation_accepts_typed_reference_placeholder() -> None:
    catalog = _catalog()
    catalog["candidates"].append({
        "capability_id": 8,
        "module": "desktop-tools",
        "action": "open_file",
        "parameters": {"file_id": {"type": "integer"}},
        "execution_contract": {"input_schema": {}},
    })
    plan = ActionPlan(
        goal="Open a located file",
        catalog_hash="a" * 64,
        principal_version="b" * 20,
        actions=[
            ActionPlanItem(
                id="find",
                capability_id=7,
                capability="knowledge__search",
                arguments={"query": "report"},
                completion_check="A file is located",
            ),
            ActionPlanItem(
                id="open",
                capability_id=8,
                capability="desktop-tools__open_file",
                arguments={"file_id": "${find.references[0].id}"},
                depends_on=["find"],
                completion_check="The file is opened",
            ),
        ],
        final_completion_check="The file is open",
    )

    assert ActionPlanValidator(user_id=4, catalog=catalog).validate_plan(plan)


def test_plan_validation_rejects_reference_without_dependency() -> None:
    action = ActionPlanItem(
        id="a2",
        capability_id=7,
        capability="knowledge__search",
        arguments={"query": "${a1.references[0].id}"},
        completion_check="Query a reference",
    )
    plan = ActionPlan(
        goal="Search",
        catalog_hash="a" * 64,
        principal_version="b" * 20,
        actions=[
            ActionPlanItem(
                id="a1",
                capability_id=7,
                capability="knowledge__search",
                arguments={"query": "first"},
                completion_check="First search completes",
            ),
            action,
        ],
        final_completion_check="Search completes",
    )

    with pytest.raises(ActionPlanValidationError) as exc_info:
        ActionPlanValidator(user_id=4, catalog=_catalog()).validate_plan(plan)

    assert any(issue.code == "missing_reference_dependency" for issue in exc_info.value.issues)
