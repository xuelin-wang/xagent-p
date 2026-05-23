from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from xagent.agent_flow.models import (
    AgentError,
    AgentFlowState,
    FlowStage,
    RunStatus,
    StepStatus,
)
from xagent.agent_persistence.repositories import (
    CheckpointRecord,
    StepEvent,
    StepEventType,
    StepRecord,
)


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._states: dict[str, AgentFlowState] = {}

    async def create_run(self, state: AgentFlowState) -> None:
        if state.run_id in self._states:
            raise ValueError(f"Run already exists: {state.run_id}")
        self._states[state.run_id] = state.model_copy(deep=True)

    async def get_run_state(self, run_id: str) -> AgentFlowState:
        state = self._states.get(run_id)
        if state is None:
            raise KeyError(f"Run not found: {run_id}")
        return state.model_copy(deep=True)

    async def update_run_state(self, state: AgentFlowState) -> None:
        if state.run_id not in self._states:
            raise KeyError(f"Run not found: {state.run_id}")
        self._states[state.run_id] = state.model_copy(deep=True)

    async def mark_completed(self, run_id: str, final_response: str) -> None:
        state = await self.get_run_state(run_id)
        state.status = RunStatus.COMPLETED
        state.current_stage = FlowStage.COMPLETED
        state.final_response = final_response
        self._states[run_id] = state

    async def mark_failed(self, run_id: str, error: dict[str, Any]) -> None:
        state = await self.get_run_state(run_id)
        state.status = RunStatus.FAILED
        state.current_stage = FlowStage.FAILED
        state.errors.append(
            AgentError(
                stage=str(error.get("stage", FlowStage.FAILED)),
                step_name=error.get("step_name"),
                message=str(error.get("message", "Agent run failed.")),
                error_type=error.get("error_type"),
                retryable=bool(error.get("retryable", False)),
                details=error.get("details", {}),
            )
        )
        self._states[run_id] = state


class InMemoryStepRepository:
    def __init__(self) -> None:
        self._steps_by_id: dict[str, StepRecord] = {}
        self._step_ids_by_key: dict[tuple[str, int, str], str] = {}
        self._step_ids_by_idempotency_key: dict[str, str] = {}
        self._events: list[StepEvent] = []
        self._event_ids: set[str] = set()
        self._event_ids_by_logical_key: dict[tuple[str, StepEventType, int], str] = {}
        self._event_sequence = 0

    async def create_or_get_step(
        self,
        *,
        run_id: str,
        iteration: int,
        step_name: str,
        step_type: str,
        input_json: dict[str, Any],
        max_attempts: int,
        idempotency_key: str,
    ) -> StepRecord:
        existing_id = self._step_ids_by_key.get((run_id, iteration, step_name))
        if existing_id is not None:
            return self._copy_step(existing_id)

        existing_idempotent_id = self._step_ids_by_idempotency_key.get(idempotency_key)
        if existing_idempotent_id is not None:
            return self._copy_step(existing_idempotent_id)

        step = StepRecord(
            step_id=f"step_{uuid4().hex}",
            run_id=run_id,
            iteration=iteration,
            step_name=step_name,
            step_type=step_type,
            status=StepStatus.PENDING,
            input_json=input_json.copy(),
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
        )
        self._steps_by_id[step.step_id] = step
        self._step_ids_by_key[(run_id, iteration, step_name)] = step.step_id
        self._step_ids_by_idempotency_key[idempotency_key] = step.step_id
        self._append_new_step_event(step, StepEventType.CREATED)
        return step.model_copy(deep=True)

    async def mark_step_running(self, step_id: str) -> StepRecord:
        step = self._get_step(step_id)
        updated = step.model_copy(
            update={
                "status": StepStatus.RUNNING,
                "attempt_count": step.attempt_count + 1,
            }
        )
        self._steps_by_id[step_id] = updated
        self._append_new_step_event(updated, StepEventType.STARTED)
        return updated.model_copy(deep=True)

    async def mark_step_succeeded(
        self,
        step_id: str,
        output_json: dict[str, Any],
    ) -> StepRecord:
        step = self._get_step(step_id)
        updated = step.model_copy(
            update={
                "status": StepStatus.SUCCEEDED,
                "output_json": output_json.copy(),
                "error_json": None,
            },
            deep=True,
        )
        self._steps_by_id[step_id] = updated
        self._append_new_step_event(updated, StepEventType.SUCCEEDED)
        return updated.model_copy(deep=True)

    async def mark_step_failed(
        self,
        step_id: str,
        error_json: dict[str, Any],
    ) -> StepRecord:
        step = self._get_step(step_id)
        updated = step.model_copy(
            update={
                "status": StepStatus.FAILED,
                "error_json": error_json.copy(),
            },
            deep=True,
        )
        self._steps_by_id[step_id] = updated
        self._append_new_step_event(updated, StepEventType.FAILED)
        return updated.model_copy(deep=True)

    async def get_steps_for_run_iteration(
        self,
        run_id: str,
        iteration: int,
    ) -> list[StepRecord]:
        return [
            step.model_copy(deep=True)
            for step in self._steps_by_id.values()
            if step.run_id == run_id and step.iteration == iteration
        ]

    async def append_step_event(self, event: StepEvent) -> StepEvent:
        if event.event_id in self._event_ids:
            return self._copy_event(event.event_id)

        event_copy = event.model_copy(deep=True)
        self._events.append(event_copy)
        self._event_ids.add(event_copy.event_id)
        self._event_sequence = max(self._event_sequence, event_copy.sequence_index)
        await self.rebuild_step_projection()
        return event_copy.model_copy(deep=True)

    async def get_step_events_for_run(self, run_id: str) -> list[StepEvent]:
        return [
            event.model_copy(deep=True)
            for event in self._events
            if event.run_id == run_id
        ]

    async def get_step_events_for_step(self, step_id: str) -> list[StepEvent]:
        return [
            event.model_copy(deep=True)
            for event in self._events
            if event.step_id == step_id
        ]

    async def get_latest_succeeded_event(self, run_id: str) -> StepEvent | None:
        for event in reversed(self._events):
            if event.run_id == run_id and event.event_type is StepEventType.SUCCEEDED:
                return event.model_copy(deep=True)
        return None

    async def rebuild_step_projection(self) -> list[StepRecord]:
        projection = self._derive_step_projection(self._events)
        self._steps_by_id = {step.step_id: step for step in projection}
        self._step_ids_by_key = {
            (step.run_id, step.iteration, step.step_name): step.step_id
            for step in projection
        }
        self._step_ids_by_idempotency_key = {
            step.idempotency_key: step.step_id for step in projection
        }
        return [step.model_copy(deep=True) for step in projection]

    def _get_step(self, step_id: str) -> StepRecord:
        step = self._steps_by_id.get(step_id)
        if step is None:
            raise KeyError(f"Step not found: {step_id}")
        return step

    def _copy_step(self, step_id: str) -> StepRecord:
        return self._get_step(step_id).model_copy(deep=True)

    def _append_new_step_event(
        self,
        step: StepRecord,
        event_type: StepEventType,
    ) -> StepEvent:
        logical_key = (step.step_id, event_type, step.attempt_count)
        existing_event_id = self._event_ids_by_logical_key.get(logical_key)
        if existing_event_id is not None:
            return self._copy_event(existing_event_id)

        self._event_sequence += 1
        event = StepEvent(
            event_id=f"step_event_{uuid4().hex}",
            run_id=step.run_id,
            step_id=step.step_id,
            sequence_index=self._event_sequence,
            iteration_index=step.iteration,
            step_name=step.step_name,
            step_type=step.step_type,
            attempt_index=step.attempt_count,
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            input_json=step.input_json.copy(),
            output_json=step.output_json.copy()
            if step.output_json is not None
            else None,
            error_json=step.error_json.copy() if step.error_json is not None else None,
            max_attempts=step.max_attempts,
            idempotency_key=step.idempotency_key,
        )
        self._events.append(event)
        self._event_ids.add(event.event_id)
        self._event_ids_by_logical_key[logical_key] = event.event_id
        return event.model_copy(deep=True)

    def _copy_event(self, event_id: str) -> StepEvent:
        for event in self._events:
            if event.event_id == event_id:
                return event.model_copy(deep=True)
        raise KeyError(f"Step event not found: {event_id}")

    def _derive_step_projection(self, events: list[StepEvent]) -> list[StepRecord]:
        projected: dict[str, StepRecord] = {}
        for event in sorted(events, key=lambda item: item.sequence_index):
            current = projected.get(event.step_id)
            if current is None:
                current = StepRecord(
                    step_id=event.step_id,
                    run_id=event.run_id,
                    iteration=event.iteration_index,
                    step_name=event.step_name,
                    step_type=event.step_type,
                    status=StepStatus.PENDING,
                    input_json=event.input_json.copy(),
                    max_attempts=event.max_attempts,
                    idempotency_key=event.idempotency_key,
                )

            status = {
                StepEventType.CREATED: StepStatus.PENDING,
                StepEventType.STARTED: StepStatus.RUNNING,
                StepEventType.SUCCEEDED: StepStatus.SUCCEEDED,
                StepEventType.FAILED: StepStatus.FAILED,
            }[event.event_type]
            projected[event.step_id] = current.model_copy(
                update={
                    "status": status,
                    "input_json": event.input_json.copy(),
                    "output_json": (
                        event.output_json.copy()
                        if event.output_json is not None
                        else current.output_json
                    ),
                    "error_json": (
                        event.error_json.copy()
                        if event.error_json is not None
                        else (
                            None
                            if event.event_type is StepEventType.SUCCEEDED
                            else current.error_json
                        )
                    ),
                    "attempt_count": max(current.attempt_count, event.attempt_index),
                    "max_attempts": event.max_attempts,
                    "idempotency_key": event.idempotency_key,
                },
                deep=True,
            )
        return list(projected.values())


class InMemoryCheckpointRepository:
    def __init__(self) -> None:
        self._checkpoints: list[CheckpointRecord] = []
        self._sequence = 0

    async def save_checkpoint(
        self,
        *,
        run_id: str,
        iteration: int,
        checkpoint_name: str,
        stage: str,
        state: AgentFlowState,
    ) -> CheckpointRecord:
        self._sequence += 1
        checkpoint = CheckpointRecord(
            checkpoint_id=f"checkpoint_{uuid4().hex}",
            run_id=run_id,
            iteration=iteration,
            checkpoint_name=checkpoint_name,
            stage=stage,
            state=state.model_copy(deep=True),
            sequence=self._sequence,
        )
        self._checkpoints.append(checkpoint)
        return checkpoint.model_copy(deep=True)

    async def get_latest_checkpoint(self, run_id: str) -> AgentFlowState | None:
        matching = [
            checkpoint
            for checkpoint in self._checkpoints
            if checkpoint.run_id == run_id
        ]
        if not matching:
            return None
        latest = max(matching, key=lambda checkpoint: checkpoint.sequence)
        return latest.state.model_copy(deep=True)
