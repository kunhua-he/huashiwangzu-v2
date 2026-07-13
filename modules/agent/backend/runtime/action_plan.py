from __future__ import annotations

from enum import StrEnum

from app.schemas.platform_resource import ResourceRef, ResourceType
from pydantic import BaseModel, Field, model_validator

ResourceRefType = ResourceType


class ActionState(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ActionPlanItem(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    capability_id: int = Field(gt=0)
    capability: str = Field(pattern=r"^[A-Za-z0-9_-]+__[A-Za-z0-9_-]+$")
    arguments: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    expected_references: list[ResourceRefType] = Field(default_factory=list)
    completion_check: str = Field(min_length=1, max_length=1000)
    approval_reason: str = Field(default="", max_length=1000)


class ActionPlan(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    catalog_hash: str = Field(min_length=16, max_length=128)
    principal_version: str = Field(min_length=8, max_length=128)
    actions: list[ActionPlanItem] = Field(min_length=1, max_length=64)
    final_completion_check: str = Field(min_length=1, max_length=2000)
    need_user_input: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_graph(self) -> "ActionPlan":
        action_ids = [item.id for item in self.actions]
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("action ids must be unique")
        known = set(action_ids)
        dependencies = {item.id: set(item.depends_on) for item in self.actions}
        for action_id, required in dependencies.items():
            if action_id in required:
                raise ValueError(f"action {action_id} cannot depend on itself")
            unknown = required - known
            if unknown:
                raise ValueError(f"action {action_id} has unknown dependencies: {sorted(unknown)}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(action_id: str) -> None:
            if action_id in visiting:
                raise ValueError("action dependencies must be acyclic")
            if action_id in visited:
                return
            visiting.add(action_id)
            for dependency in dependencies[action_id]:
                visit(dependency)
            visiting.remove(action_id)
            visited.add(action_id)

        for action_id in action_ids:
            visit(action_id)
        return self


class ActionObservation(BaseModel):
    action_id: str
    state: ActionState
    attempt: int = Field(default=0, ge=0)
    result_summary: str = ""
    error_class: str = ""
    retryable: bool = False
    references: list[ResourceRef] = Field(default_factory=list)
    argument_hash: str = ""
    result_hash: str = ""


class ActionPlanCheckpoint(BaseModel):
    plan: ActionPlan
    observations: dict[str, ActionObservation] = Field(default_factory=dict)
    planning_round: int = Field(default=1, ge=1, le=10)
    experience_submitted: bool = False
    experience_id: int | None = Field(default=None, gt=0)

    def ready_action_ids(self) -> list[str]:
        completed = {
            action_id
            for action_id, observation in self.observations.items()
            if observation.state == ActionState.COMPLETED
        }
        terminal = {
            action_id
            for action_id, observation in self.observations.items()
            if observation.state in {
                ActionState.RUNNING,
                ActionState.COMPLETED,
                ActionState.FAILED,
                ActionState.BLOCKED,
                ActionState.CANCELLED,
            }
        }
        return [
            item.id
            for item in self.plan.actions
            if item.id not in terminal and set(item.depends_on) <= completed
        ]

    def reconcile_interrupted_actions(self, catalog: dict) -> None:
        """Resolve process-local RUNNING states before a structured resume."""
        candidates = {
            f"{item.get('module')}__{item.get('action')}": item
            for item in catalog.get("candidates", [])
            if isinstance(item, dict)
        }
        for action in self.plan.actions:
            observation = self.observations.get(action.id)
            if observation is None or observation.state != ActionState.RUNNING:
                continue
            contract = (candidates.get(action.capability) or {}).get("execution_contract") or {}
            if str(contract.get("side_effect_level") or "none") == "none":
                self.observations[action.id] = observation.model_copy(
                    update={
                        "state": ActionState.PENDING,
                        "result_summary": "Read-only action was interrupted and may be resumed.",
                        "error_class": "action_interrupted",
                        "retryable": True,
                    },
                )
                continue
            self.observations[action.id] = observation.model_copy(
                update={
                    "state": ActionState.BLOCKED,
                    "result_summary": (
                        "Side-effecting action was interrupted before completion could be proven."
                    ),
                    "error_class": "action_interrupted_requires_confirmation",
                    "retryable": False,
                },
            )
def resource_refs_from_result(result: object) -> list[ResourceRef]:
    if not isinstance(result, dict):
        return []
    payload = result.get("data", result)
    if not isinstance(payload, dict):
        return []
    raw_references = payload.get("resource_refs", payload.get("references", []))
    if not isinstance(raw_references, list):
        return []
    references: list[ResourceRef] = []
    for value in raw_references:
        if not isinstance(value, dict):
            continue
        try:
            references.append(ResourceRef.model_validate(value))
        except ValueError:
            continue
    return references
