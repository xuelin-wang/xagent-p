import asyncio

from xagent.agent_flow.models import AgentFlowState, FlowStage, RunStatus, StepStatus
from xagent.agent_persistence.memory import (
    InMemoryCheckpointRepository,
    InMemoryRunRepository,
    InMemoryStepRepository,
)


def test_run_repository_stores_copies_and_marks_terminal_states() -> None:
    asyncio.run(_run_repository_stores_copies_and_marks_terminal_states())


async def _run_repository_stores_copies_and_marks_terminal_states() -> None:
    repository = InMemoryRunRepository()
    state = AgentFlowState(run_id="run_1", user_query="diagnose no start")

    await repository.create_run(state)
    state.metadata["local_mutation"] = True

    stored = await repository.get_run_state("run_1")
    assert stored.metadata == {}

    stored.metadata["read_mutation"] = True
    reread = await repository.get_run_state("run_1")
    assert reread.metadata == {}

    await repository.mark_completed("run_1", "done")
    completed = await repository.get_run_state("run_1")
    assert completed.status is RunStatus.COMPLETED
    assert completed.current_stage is FlowStage.COMPLETED
    assert completed.final_response == "done"

    await repository.mark_failed("run_1", {"message": "late failure"})
    failed = await repository.get_run_state("run_1")
    assert failed.status is RunStatus.FAILED
    assert failed.current_stage is FlowStage.FAILED
    assert failed.errors[-1].message == "late failure"


def test_step_repository_create_or_get_is_idempotent_and_tracks_attempts() -> None:
    asyncio.run(_step_repository_create_or_get_is_idempotent_and_tracks_attempts())


async def _step_repository_create_or_get_is_idempotent_and_tracks_attempts() -> None:
    repository = InMemoryStepRepository()

    created = await repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": "diagnose no start"},
        max_attempts=2,
        idempotency_key="run_1:0:planner",
    )
    fetched = await repository.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="planner",
        step_type="planner",
        input_json={"query": "different"},
        max_attempts=9,
        idempotency_key="run_1:0:planner",
    )

    assert fetched == created

    running = await repository.mark_step_running(created.step_id)
    assert running.status is StepStatus.RUNNING
    assert running.attempt_count == 1

    failed = await repository.mark_step_failed(created.step_id, {"message": "bad json"})
    assert failed.status is StepStatus.FAILED
    assert failed.error_json == {"message": "bad json"}

    succeeded = await repository.mark_step_succeeded(
        created.step_id,
        {"goal": "inspect history"},
    )
    assert succeeded.status is StepStatus.SUCCEEDED
    assert succeeded.output_json == {"goal": "inspect history"}
    assert succeeded.error_json is None

    steps = await repository.get_steps_for_run_iteration("run_1", 0)
    assert steps == [succeeded]


def test_checkpoint_repository_returns_latest_checkpoint_copy() -> None:
    asyncio.run(_checkpoint_repository_returns_latest_checkpoint_copy())


async def _checkpoint_repository_returns_latest_checkpoint_copy() -> None:
    repository = InMemoryCheckpointRepository()
    first = AgentFlowState(run_id="run_1", user_query="diagnose no start")
    second = first.model_copy(update={"current_stage": FlowStage.PLANNING})

    await repository.save_checkpoint(
        run_id="run_1",
        iteration=0,
        checkpoint_name="start",
        stage="start",
        state=first,
    )
    await repository.save_checkpoint(
        run_id="run_1",
        iteration=0,
        checkpoint_name="planner",
        stage="planning",
        state=second,
    )

    latest = await repository.get_latest_checkpoint("run_1")
    assert latest is not None
    assert latest.current_stage is FlowStage.PLANNING

    latest.metadata["mutated"] = True
    reread = await repository.get_latest_checkpoint("run_1")
    assert reread is not None
    assert reread.metadata == {}


def test_checkpoint_repository_returns_none_when_run_has_no_checkpoint() -> None:
    asyncio.run(_checkpoint_repository_returns_none_when_run_has_no_checkpoint())


async def _checkpoint_repository_returns_none_when_run_has_no_checkpoint() -> None:
    repository = InMemoryCheckpointRepository()

    assert await repository.get_latest_checkpoint("missing") is None
