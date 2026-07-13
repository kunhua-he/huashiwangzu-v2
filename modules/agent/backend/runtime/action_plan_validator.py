from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from ..services.capability_catalog import (
    normalize_json_schema,
    parameter_schema,
    validate_execution_snapshot,
)
from .action_plan import ActionObservation, ActionPlan, ActionPlanItem, ActionState

_REFERENCE_RE = re.compile(
    r"^\$\{(?P<action>[A-Za-z][A-Za-z0-9_-]{0,63})\.references\[(?P<index>\d+)]\.(?P<field>id|locator)}$"
)


@dataclass(frozen=True)
class PlanValidationIssue:
    action_id: str
    code: str
    message: str


class ActionPlanValidationError(ValueError):
    def __init__(self, issues: list[PlanValidationIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{item.action_id}:{item.code}" for item in issues))


class ActionPlanValidator:
    def __init__(self, *, user_id: int, catalog: dict) -> None:
        self.user_id = int(user_id)
        self.catalog = catalog
        self._candidates = {
            f"{item.get('module')}__{item.get('action')}": item
            for item in catalog.get("candidates", [])
            if isinstance(item, dict)
        }

    def validate_plan(self, plan: ActionPlan) -> ActionPlan:
        issues: list[PlanValidationIssue] = []
        principal = self.catalog.get("principal") or {}
        if plan.catalog_hash != self.catalog.get("catalog_hash"):
            issues.append(PlanValidationIssue("plan", "stale_catalog", "catalog hash changed"))
        if plan.principal_version != principal.get("profile_version"):
            issues.append(PlanValidationIssue("plan", "stale_principal", "principal version changed"))
        for action in plan.actions:
            candidate = self._candidates.get(action.capability)
            if not candidate or int(candidate.get("capability_id") or 0) != action.capability_id:
                issues.append(PlanValidationIssue(
                    action.id,
                    "capability_not_authorized",
                    "capability identity is absent from the SQL-authorized catalog",
                ))
                continue
            contract = candidate.get("execution_contract") or {}
            schema = normalize_json_schema(
                contract.get("input_schema") or parameter_schema(candidate.get("parameters") or {}),
            )
            validation_arguments = self._plan_validation_arguments(
                action,
                schema,
                issues,
            )
            for error in Draft202012Validator(schema).iter_errors(validation_arguments):
                issues.append(PlanValidationIssue(
                    action.id,
                    "invalid_arguments",
                    error.message,
                ))
        if issues:
            raise ActionPlanValidationError(issues)
        return plan

    @staticmethod
    def _plan_validation_arguments(
        action: ActionPlanItem,
        schema: dict,
        issues: list[PlanValidationIssue],
    ) -> dict:
        def materialize(value: object, value_schema: dict) -> object:
            if not isinstance(value_schema, dict):
                value_schema = {}
            if isinstance(value, dict):
                properties = value_schema.get("properties") or {}
                additional = value_schema.get("additionalProperties") or {}
                return {
                    str(key): materialize(
                        item,
                        properties.get(str(key), additional)
                        if isinstance(properties, dict)
                        else additional,
                    )
                    for key, item in value.items()
                }
            if isinstance(value, list):
                item_schema = value_schema.get("items") or {}
                return [materialize(item, item_schema) for item in value]
            if not isinstance(value, str) or "${" not in value:
                return value
            match = _REFERENCE_RE.fullmatch(value)
            if not match:
                issues.append(PlanValidationIssue(
                    action.id,
                    "invalid_resource_reference",
                    "resource references must occupy the complete argument value",
                ))
                return value
            source_action = match.group("action")
            if source_action not in action.depends_on:
                issues.append(PlanValidationIssue(
                    action.id,
                    "missing_reference_dependency",
                    f"action must depend on referenced action {source_action}",
                ))
            return _placeholder_for_schema(value_schema)

        materialized = materialize(action.arguments, schema)
        return materialized if isinstance(materialized, dict) else action.arguments

    def bind_arguments(
        self,
        action: ActionPlanItem,
        observations: dict[str, ActionObservation],
    ) -> dict:
        def bind(value: object) -> object:
            if isinstance(value, list):
                return [bind(item) for item in value]
            if isinstance(value, dict):
                return {str(key): bind(item) for key, item in value.items()}
            if not isinstance(value, str) or "${" not in value:
                return value
            match = _REFERENCE_RE.fullmatch(value)
            if not match:
                raise ValueError("resource references must occupy the complete argument value")
            source_action = match.group("action")
            if source_action not in action.depends_on:
                raise ValueError(f"action {action.id} must depend on referenced action {source_action}")
            observation = observations.get(source_action)
            if not observation or observation.state != ActionState.COMPLETED:
                raise ValueError(f"referenced action {source_action} is not completed")
            reference_index = int(match.group("index"))
            if reference_index >= len(observation.references):
                raise ValueError(f"reference index {reference_index} is unavailable")
            reference = observation.references[reference_index]
            return getattr(reference, match.group("field"))

        return bind(deepcopy(action.arguments))  # type: ignore[return-value]

    async def validate_before_execution(self, action: ActionPlanItem) -> dict:
        return await validate_execution_snapshot(
            user_id=self.user_id,
            expected_catalog_hash=self.catalog["catalog_hash"],
            capability_id=action.capability_id,
            capability_name=action.capability,
        )


def _placeholder_for_schema(schema: dict) -> object:
    variants = schema.get("anyOf") or schema.get("oneOf") or []
    if isinstance(variants, list) and variants:
        return _placeholder_for_schema(variants[0] if isinstance(variants[0], dict) else {})
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "string")
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    return "resource-reference"
