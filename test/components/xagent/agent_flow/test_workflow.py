"""Tests for composite step hierarchy and iteration workflow tree.

Design link: Section 3.1, step hierarchy.
"""

import asyncio

from xagent.agent_flow.models import (
    AgentFlowState,
    PlanSubagentSelection,
    StepStatus,
    SummaryDecision,
)
from xagent.agent_flow.planner import FakePlannerExecutor, PlannerStep
from xagent.agent_flow.step_runner import ChildStep, StepRunner
from xagent.agent_flow.steps import (
    ParallelStepGroup,
    RetryPolicy,
    RuntimeContext,
    SequenceStepGroup,
    StepExecutionPolicy,
    StepResult,
)
from xagent.agent_flow.subagents import FakeFlowSubagent, SubagentStep
from xagent.agent_flow.summary import FakeSummaryExecutor, SummaryStep
from xagent.agent_persistence.memory import InMemoryStepRepository

from .test_executors import _subagent_configs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(run_id: str = "run_1") -> AgentFlowState:
    return AgentFlowState(run_id=run_id, user_query="diagnose no start")


def _planner_child(state: AgentFlowState) -> ChildStep:
    subagents = _subagent_configs()
    return ChildStep(
        step=PlannerStep(
            executor=FakePlannerExecutor(selection_names=["manuals"]),
            subagents=subagents,
            max_selections=1,
        ),
        step_name="planner",
        input_json={"query": state.user_query},
    )


def _subagent_child(name: str) -> ChildStep:
    selection = PlanSubagentSelection(name=name)
    return ChildStep(
        step=SubagentStep(
            subagent=FakeFlowSubagent(name=name),
            selection=selection,
        ),
        step_name=f"subagent:{name}",
        input_json=selection.model_dump(mode="json"),
    )


def _summary_child(state: AgentFlowState) -> ChildStep:
    iteration = state.get_or_create_current_iteration()
    return ChildStep(
        step=SummaryStep(
            executor=FakeSummaryExecutor(decision=SummaryDecision.FINAL),
            iteration=iteration,
        ),
        step_name="summary",
        input_json={},
    )


# ---------------------------------------------------------------------------
# SequenceStepGroup
# ---------------------------------------------------------------------------


def test_sequence_step_group_runs_children_in_order() -> None:
    asyncio.run(_sequence_step_group_runs_children_in_order())


async def _sequence_step_group_runs_children_in_order() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()
    order: list[str] = []

    async def record(name: str) -> StepResult:
        order.append(name)
        return StepResult(output_json={"name": name})

    class _NamedStep:
        def __init__(self, name: str) -> None:
            self.step_type = f"fake:{name}"
            self._name = name

        async def run(
            self, state: AgentFlowState, context: RuntimeContext
        ) -> StepResult:
            return await record(self._name)

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[
            ChildStep(step=_NamedStep("a"), step_name="a", input_json={}),
            ChildStep(step=_NamedStep("b"), step_name="b", input_json={}),
            ChildStep(step=_NamedStep("c"), step_name="c", input_json={}),
        ],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    assert order == ["a", "b", "c"]
    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    step_names = {s.step_name for s in steps}
    assert {"test_seq", "a", "b", "c"} == step_names


def test_sequence_step_group_skips_none_from_lazy_child() -> None:
    asyncio.run(_sequence_step_group_skips_none_from_lazy_child())


async def _sequence_step_group_skips_none_from_lazy_child() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()
    ran: list[str] = []

    class _TrackStep:
        step_type = "fake:track"

        def __init__(self, name: str) -> None:
            self._name = name

        async def run(
            self, state: AgentFlowState, context: RuntimeContext
        ) -> StepResult:
            ran.append(self._name)
            return StepResult(output_json={})

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[
            ChildStep(step=_TrackStep("a"), step_name="a", input_json={}),
            lambda _: None,  # skipped
            ChildStep(step=_TrackStep("b"), step_name="b", input_json={}),
        ],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    assert ran == ["a", "b"]


def test_sequence_step_group_creates_step_record_for_group() -> None:
    asyncio.run(_sequence_step_group_creates_step_record_for_group())


async def _sequence_step_group_creates_step_record_for_group() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="my_seq",
        children=[_planner_child(state)],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    names = {s.step_name for s in steps}
    assert "my_seq" in names
    seq_step = next(s for s in steps if s.step_name == "my_seq")
    assert seq_step.status is StepStatus.SUCCEEDED
    assert seq_step.step_type == "sequence:test"


# ---------------------------------------------------------------------------
# ParallelStepGroup
# ---------------------------------------------------------------------------


def test_parallel_step_group_runs_children_concurrently() -> None:
    asyncio.run(_parallel_step_group_runs_children_concurrently())


async def _parallel_step_group_runs_children_concurrently() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    group = ParallelStepGroup(
        step_type="parallel:test",
        step_name="test_par",
        children=[_subagent_child("manuals"), _subagent_child("history")],
    )

    result = await runner.execute_composite(group, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    step_names = {s.step_name for s in steps}
    assert {"test_par", "subagent:manuals", "subagent:history"} == step_names
    _ = result  # both children ran; output is merged dict


def test_parallel_step_group_factory_children() -> None:
    asyncio.run(_parallel_step_group_factory_children())


async def _parallel_step_group_factory_children() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    def build_children(s: AgentFlowState) -> list[ChildStep]:
        return [_subagent_child("manuals"), _subagent_child("history")]

    group = ParallelStepGroup(
        step_type="parallel:test",
        step_name="test_par",
        children=build_children,
    )

    await runner.execute_composite(group, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    step_names = {s.step_name for s in steps}
    assert {"test_par", "subagent:manuals", "subagent:history"} == step_names


def test_parallel_step_group_children_have_parent_step_id() -> None:
    asyncio.run(_parallel_step_group_children_have_parent_step_id())


async def _parallel_step_group_children_have_parent_step_id() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    group = ParallelStepGroup(
        step_type="parallel:test",
        step_name="par_group",
        children=[_subagent_child("manuals"), _subagent_child("history")],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    group_step = next(s for s in steps if s.step_name == "par_group")
    for step in steps:
        if step.step_name in {"subagent:manuals", "subagent:history"}:
            assert step.parent_step_id == group_step.step_id


# ---------------------------------------------------------------------------
# Resume within composites
# ---------------------------------------------------------------------------


def test_parallel_resume_skips_already_succeeded_children() -> None:
    asyncio.run(_parallel_resume_skips_already_succeeded_children())


async def _parallel_resume_skips_already_succeeded_children() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    called: list[str] = []

    class _TrackSubagent:
        def __init__(self, name: str) -> None:
            self.name = name
            self.description = f"tracks {name}"

        async def ainvoke(
            self,
            *,
            state: AgentFlowState,
            selection: PlanSubagentSelection,
        ) -> None:
            from xagent.agent_flow.models import SubagentResult

            called.append(self.name)
            return SubagentResult(name=self.name, status="completed", content=self.name)

    selection_a = PlanSubagentSelection(name="alpha")
    selection_b = PlanSubagentSelection(name="beta")

    # Pre-mark alpha as already succeeded
    alpha_step = await repo.create_or_get_step(
        run_id="run_1",
        iteration=0,
        step_name="subagent:alpha",
        step_type="subagent",
        input_json={},
        max_attempts=1,
        idempotency_key="run_1:0:subagent:alpha",
    )
    from xagent.agent_flow.models import SubagentResult

    await repo.mark_step_succeeded(
        alpha_step.step_id,
        SubagentResult(
            name="alpha", status="completed", content="alpha result"
        ).model_dump(mode="json"),
    )

    group = ParallelStepGroup(
        step_type="parallel:subagents",
        step_name="subagents",
        children=[
            ChildStep(
                step=SubagentStep(
                    subagent=_TrackSubagent("alpha"), selection=selection_a
                ),
                step_name="subagent:alpha",
                input_json=selection_a.model_dump(mode="json"),
            ),
            ChildStep(
                step=SubagentStep(
                    subagent=_TrackSubagent("beta"), selection=selection_b
                ),
                step_name="subagent:beta",
                input_json=selection_b.model_dump(mode="json"),
            ),
        ],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    assert called == ["beta"]  # alpha was skipped; beta ran


# ---------------------------------------------------------------------------
# Nested composites
# ---------------------------------------------------------------------------


def test_nested_composite_sequence_inside_parallel() -> None:
    asyncio.run(_nested_composite_sequence_inside_parallel())


async def _nested_composite_sequence_inside_parallel() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    inner_seq = SequenceStepGroup(
        step_type="sequence:inner",
        step_name="inner_seq",
        children=[_subagent_child("manuals")],
    )

    outer_par = ParallelStepGroup(
        step_type="parallel:outer",
        step_name="outer_par",
        children=[
            ChildStep(step=inner_seq, step_name="inner_seq", input_json={}),
            _subagent_child("history"),
        ],
    )

    await runner.execute_composite(outer_par, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    step_names = {s.step_name for s in steps}
    assert {
        "outer_par",
        "inner_seq",
        "subagent:manuals",
        "subagent:history",
    } == step_names


# ---------------------------------------------------------------------------
# ChildStep context override
# ---------------------------------------------------------------------------


def test_child_step_inherits_parent_context_when_none() -> None:
    asyncio.run(_child_step_inherits_parent_context_when_none())


async def _child_step_inherits_parent_context_when_none() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()
    subagents = _subagent_configs()

    parent_context = RuntimeContext(
        execution_policy=StepExecutionPolicy(retry=RetryPolicy(max_attempts=3))
    )

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[
            ChildStep(
                step=PlannerStep(
                    executor=FakePlannerExecutor(selection_names=["manuals"]),
                    subagents=subagents,
                    max_selections=1,
                ),
                step_name="planner",
                input_json={},
                context=None,  # should inherit parent_context
            )
        ],
    )

    await runner.execute_composite(group, state, parent_context)

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    planner_step = next(s for s in steps if s.step_name == "planner")
    assert planner_step.max_attempts == 3


def test_child_step_uses_own_context_when_set() -> None:
    asyncio.run(_child_step_uses_own_context_when_set())


async def _child_step_uses_own_context_when_set() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()
    subagents = _subagent_configs()

    parent_context = RuntimeContext(
        execution_policy=StepExecutionPolicy(retry=RetryPolicy(max_attempts=1))
    )
    child_context = RuntimeContext(
        execution_policy=StepExecutionPolicy(retry=RetryPolicy(max_attempts=5))
    )

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[
            ChildStep(
                step=PlannerStep(
                    executor=FakePlannerExecutor(selection_names=["manuals"]),
                    subagents=subagents,
                    max_selections=1,
                ),
                step_name="planner",
                input_json={},
                context=child_context,
            )
        ],
    )

    await runner.execute_composite(group, state, parent_context)

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    planner_step = next(s for s in steps if s.step_name == "planner")
    assert planner_step.max_attempts == 5


# ---------------------------------------------------------------------------
# Dynamic input_json callable
# ---------------------------------------------------------------------------


def test_child_step_dynamic_input_json() -> None:
    asyncio.run(_child_step_dynamic_input_json())


async def _child_step_dynamic_input_json() -> None:
    repo = InMemoryStepRepository()
    runner = StepRunner(repo)
    state = _state()

    class _RecordInput:
        step_type = "fake"

        async def run(
            self, state: AgentFlowState, context: RuntimeContext
        ) -> StepResult:
            return StepResult(output_json={})

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[
            ChildStep(
                step=_RecordInput(),
                step_name="recorder",
                input_json=lambda s: {"query": s.user_query, "dynamic": True},
            )
        ],
    )

    await runner.execute_composite(group, state, RuntimeContext())

    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    rec_step = next(s for s in steps if s.step_name == "recorder")
    assert rec_step.input_json == {"query": "diagnose no start", "dynamic": True}


# ---------------------------------------------------------------------------
# on_success callback for composite
# ---------------------------------------------------------------------------


def test_execute_composite_calls_on_success_and_stores_checkpoint_id() -> None:
    asyncio.run(_execute_composite_calls_on_success_and_stores_checkpoint_id())


async def _execute_composite_calls_on_success_and_stores_checkpoint_id() -> None:
    from xagent.agent_persistence.memory import InMemoryCheckpointRepository
    from xagent.agent_persistence.repositories import CheckpointRecord

    repo = InMemoryStepRepository()
    ckpt_repo = InMemoryCheckpointRepository()
    runner = StepRunner(repo)
    state = _state()
    called: list[dict] = []

    async def my_on_success(output_json: dict) -> CheckpointRecord:
        called.append(output_json)
        return await ckpt_repo.save_checkpoint(
            run_id=state.run_id,
            iteration=0,
            checkpoint_name="test",
            stage="test",
            state=state,
        )

    group = SequenceStepGroup(
        step_type="sequence:test",
        step_name="test_seq",
        children=[_planner_child(state)],
    )

    await runner.execute_composite(
        group, state, RuntimeContext(), on_success=my_on_success
    )

    assert len(called) == 1
    steps = await repo.get_steps_for_run_iteration("run_1", 0)
    seq_step = next(s for s in steps if s.step_name == "test_seq")
    assert seq_step.checkpoint_id is not None
