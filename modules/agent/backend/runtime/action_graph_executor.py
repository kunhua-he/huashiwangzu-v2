from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from jsonschema import Draft202012Validator

from ..services.capability_catalog import parameter_schema
from ..services.capability_execution import capability_result_error, capability_result_succeeded
from .action_plan import (
    ActionObservation,
    ActionPlanCheckpoint,
    ActionPlanItem,
    ActionState,
    resource_refs_from_result,
)
from .action_plan_validator import ActionPlanValidator

ExecuteCallback = Callable[[ActionPlanItem, dict, dict], Awaitable[object]]
ObservationCallback = Callable[[ActionPlanCheckpoint, ActionObservation], Awaitable[None]]


class ActionGraphStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    STALLED = "stalled"


@dataclass(frozen=True)
class ActionGraphExecutionResult:
    status: ActionGraphStatus
    checkpoint: ActionPlanCheckpoint
    action_id: str = ""
    reason: str = ""


class ActionGraphExecutor:
    def __init__(
        self,
        *,
        catalog: dict,
        execute_callback: ExecuteCallback,
        validator: ActionPlanValidator | None = None,
        observation_callback: ObservationCallback | None = None,
        max_concurrency: int = 8,
    ) -> None:
        self.catalog = catalog
        self.execute_callback = execute_callback
        self.validator = validator
        self.observation_callback = observation_callback
        self.max_concurrency = max(1, int(max_concurrency))
        raw_candidates = catalog.get("candidates", catalog.get("capabilities", []))
        self._candidates = {
            f"{item.get('module')}__{item.get('action')}": item
            for item in raw_candidates
            if isinstance(item, dict) and item.get("module") and item.get("action")
        }

    async def execute(self, checkpoint: ActionPlanCheckpoint) -> ActionGraphExecutionResult:
        while True:
            failed = self._first_observation(checkpoint, ActionState.FAILED)
            if failed is not None:
                return ActionGraphExecutionResult(
                    status=ActionGraphStatus.FAILED,
                    checkpoint=checkpoint,
                    action_id=failed.action_id,
                    reason=failed.error_class or failed.result_summary,
                )
            blocked = self._first_observation(
                checkpoint,
                ActionState.BLOCKED,
                ActionState.CANCELLED,
            )
            if blocked is not None:
                return ActionGraphExecutionResult(
                    status=ActionGraphStatus.BLOCKED,
                    checkpoint=checkpoint,
                    action_id=blocked.action_id,
                    reason=blocked.error_class or blocked.result_summary,
                )

            completed_ids = {
                action_id
                for action_id, observation in checkpoint.observations.items()
                if observation.state == ActionState.COMPLETED
            }
            if len(completed_ids) == len(checkpoint.plan.actions):
                return ActionGraphExecutionResult(
                    status=ActionGraphStatus.COMPLETED,
                    checkpoint=checkpoint,
                )

            actions_by_id = {item.id: item for item in checkpoint.plan.actions}
            ready = [
                actions_by_id[action_id]
                for action_id in checkpoint.ready_action_ids()
                if action_id in actions_by_id
                and (
                    action_id not in checkpoint.observations
                    or checkpoint.observations[action_id].state
                    in {ActionState.PENDING, ActionState.READY}
                )
            ]
            if not ready:
                return ActionGraphExecutionResult(
                    status=ActionGraphStatus.STALLED,
                    checkpoint=checkpoint,
                    reason="no_ready_actions",
                )

            parallel_batch: list[ActionPlanItem] = []
            for action in ready:
                if self._parallel_safe(action):
                    parallel_batch.append(action)
                    continue
                if parallel_batch:
                    await self._execute_parallel(checkpoint, parallel_batch)
                    parallel_batch = []
                    if self._first_observation(checkpoint, ActionState.FAILED) is not None:
                        break
                await self._execute_one(checkpoint, action)
                if self._first_observation(checkpoint, ActionState.FAILED) is not None:
                    break
            else:
                if parallel_batch:
                    await self._execute_parallel(checkpoint, parallel_batch)

    @staticmethod
    def _first_observation(
        checkpoint: ActionPlanCheckpoint,
        *states: ActionState,
    ) -> ActionObservation | None:
        wanted = set(states)
        for action in checkpoint.plan.actions:
            observation = checkpoint.observations.get(action.id)
            if observation is not None and observation.state in wanted:
                return observation
        return None

    def _candidate(self, action: ActionPlanItem) -> dict | None:
        candidate = self._candidates.get(action.capability)
        if candidate is None:
            return None
        if int(candidate.get("capability_id") or 0) != action.capability_id:
            return None
        return candidate

    def _parallel_safe(self, action: ActionPlanItem) -> bool:
        candidate = self._candidate(action) or {}
        contract = candidate.get("execution_contract") or {}
        return (
            contract.get("parallel_safe") is True
            and str(contract.get("side_effect_level") or "none") == "none"
        )

    async def _execute_parallel(
        self,
        checkpoint: ActionPlanCheckpoint,
        actions: list[ActionPlanItem],
    ) -> None:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run(action: ActionPlanItem) -> None:
            async with semaphore:
                await self._execute_one(checkpoint, action)

        await asyncio.gather(*(run(action) for action in actions))

    async def _execute_one(
        self,
        checkpoint: ActionPlanCheckpoint,
        action: ActionPlanItem,
    ) -> None:
        candidate = self._candidate(action)
        if candidate is None:
            await self._record_failure(
                checkpoint,
                action,
                error_class="capability_not_authorized",
                summary="Capability identity is absent from the execution catalog.",
            )
            return
        contract = candidate.get("execution_contract") or {}

        try:
            arguments = (
                self.validator.bind_arguments(action, checkpoint.observations)
                if self.validator is not None
                else dict(action.arguments)
            )
            if self.validator is not None:
                await self.validator.validate_before_execution(action)
        except (RuntimeError, ValueError) as exc:
            await self._record_failure(
                checkpoint,
                action,
                error_class=str(exc) or type(exc).__name__,
                summary="Action validation failed before execution.",
            )
            return

        input_schema = contract.get("input_schema") or parameter_schema(
            candidate.get("parameters") or {},
        )
        input_errors = list(Draft202012Validator(input_schema).iter_errors(arguments))
        if input_errors:
            await self._record_failure(
                checkpoint,
                action,
                error_class="invalid_arguments",
                summary=input_errors[0].message,
            )
            return

        argument_payload = _json_payload(arguments)
        previous = checkpoint.observations.get(action.id)
        running = ActionObservation(
            action_id=action.id,
            state=ActionState.RUNNING,
            attempt=(previous.attempt if previous else 0) + 1,
            argument_hash=_sha256(argument_payload),
        )
        await self._set_observation(checkpoint, running)

        timeout_seconds = max(0.0, float(contract.get("timeout_seconds") or 0))
        try:
            invocation = self.execute_callback(action, arguments, contract)
            result = (
                await asyncio.wait_for(invocation, timeout=timeout_seconds)
                if timeout_seconds > 0
                else await invocation
            )
        except TimeoutError:
            await self._record_failure(
                checkpoint,
                action,
                error_class="timeout",
                summary=f"Action exceeded its {timeout_seconds:g} second timeout.",
                argument_hash=running.argument_hash,
                attempt=running.attempt,
            )
            return
        except Exception as exc:
            await self._record_failure(
                checkpoint,
                action,
                error_class=type(exc).__name__,
                summary=str(exc)[:1000],
                argument_hash=running.argument_hash,
                attempt=running.attempt,
            )
            return

        result_payload = _json_payload(result)
        references = resource_refs_from_result(result)
        for reference in references:
            reference.provenance = {
                **reference.provenance,
                "capability": action.capability,
                "action_id": action.id,
            }
        error = self._result_contract_error(action, contract, result, references)
        if not capability_result_succeeded(result):
            result_error_class = (
                str(result.get("error_class") or "")
                if isinstance(result, dict)
                else ""
            )
            if result_error_class == "approval_required":
                await self._record_terminal(
                    checkpoint,
                    action,
                    state=ActionState.BLOCKED,
                    error_class=result_error_class,
                    summary=capability_result_error(result) or "Action requires approval.",
                    argument_hash=running.argument_hash,
                    result_hash=_sha256(result_payload),
                    attempt=running.attempt,
                )
                return
            error = (
                capability_result_error(result) or "capability_execution_failed",
                result_error_class or "capability_execution_failed",
            )
        if error is not None:
            summary, error_class = error
            await self._record_failure(
                checkpoint,
                action,
                error_class=error_class,
                summary=summary,
                argument_hash=running.argument_hash,
                result_hash=_sha256(result_payload),
                attempt=running.attempt,
            )
            return

        completed = ActionObservation(
            action_id=action.id,
            state=ActionState.COMPLETED,
            attempt=running.attempt,
            result_summary=result_payload[:1000],
            references=references,
            argument_hash=running.argument_hash,
            result_hash=_sha256(result_payload),
        )
        await self._set_observation(checkpoint, completed)

    @staticmethod
    def _result_contract_error(
        action: ActionPlanItem,
        contract: dict,
        result: object,
        references: list,
    ) -> tuple[str, str] | None:
        output_schema = contract.get("output_schema")
        if isinstance(output_schema, dict) and output_schema:
            payload = result.get("data", result) if isinstance(result, dict) else result
            errors = list(Draft202012Validator(output_schema).iter_errors(payload))
            if errors:
                return errors[0].message, "invalid_capability_output"

        allowed_types = {str(item) for item in contract.get("output_reference_types", [])}
        reference_types = {item.type.value for item in references}
        invalid_types = sorted(reference_types - allowed_types) if allowed_types else []
        if invalid_types:
            return (
                f"Capability returned undeclared reference types: {', '.join(invalid_types)}",
                "invalid_output_reference_type",
            )
        actual_types = {item.type for item in references}
        missing_types = [item.value for item in action.expected_references if item not in actual_types]
        if missing_types:
            return (
                f"Action did not return expected references: {', '.join(missing_types)}",
                "missing_output_reference",
            )
        return None

    async def _record_failure(
        self,
        checkpoint: ActionPlanCheckpoint,
        action: ActionPlanItem,
        *,
        error_class: str,
        summary: str,
        argument_hash: str = "",
        result_hash: str = "",
        attempt: int | None = None,
    ) -> None:
        await self._record_terminal(
            checkpoint,
            action,
            state=ActionState.FAILED,
            error_class=error_class,
            summary=summary,
            argument_hash=argument_hash,
            result_hash=result_hash,
            attempt=attempt,
        )

    async def _record_terminal(
        self,
        checkpoint: ActionPlanCheckpoint,
        action: ActionPlanItem,
        *,
        state: ActionState,
        error_class: str,
        summary: str,
        argument_hash: str = "",
        result_hash: str = "",
        attempt: int | None = None,
    ) -> None:
        previous = checkpoint.observations.get(action.id)
        observation = ActionObservation(
            action_id=action.id,
            state=state,
            attempt=attempt if attempt is not None else (previous.attempt if previous else 0),
            result_summary=summary[:1000],
            error_class=error_class,
            retryable=False,
            argument_hash=argument_hash or (previous.argument_hash if previous else ""),
            result_hash=result_hash,
        )
        await self._set_observation(checkpoint, observation)

    async def _set_observation(
        self,
        checkpoint: ActionPlanCheckpoint,
        observation: ActionObservation,
    ) -> None:
        checkpoint.observations[observation.action_id] = observation
        if self.observation_callback is not None:
            await self.observation_callback(checkpoint, observation)


def _json_payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
