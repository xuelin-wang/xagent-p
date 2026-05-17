Design Doc: Evaluation and Config-Improvement Loop for xagent-p
1. Goal

Create a controlled loop for improving the configurable agent_flow application:

Run agent application
-> Record full run result
-> Evaluate result quality
-> Aggregate failure patterns
-> Suggest small config/prompt changes
-> Run candidate config
-> Compare baseline vs candidate
-> Recommend promotion or rejection

This system should help improve the agent by changing configurable parts such as:

- planner prompt
- summary / decision prompt
- subagent prompts
- subagent descriptions
- enabled/disabled subagents
- model choices
- max iterations
- runtime policy knobs
- retrieval/tool parameters later

The system should not directly modify production config or application code.

The LLM may suggest changes, but changes must be represented as structured, reviewable proposals and tested before promotion.

2. Non-goals

Do not implement these in the first version:

- automatic production config mutation
- code rewriting
- generic AutoML framework
- online reinforcement learning
- database-backed experiment platform
- complex UI
- LangGraph dependency
- deep integration with Phoenix/OpenTelemetry
- fully automated PR creation

Start with a local/offline file-based loop.

3. High-level architecture

Add two new components around the existing runtime:

components/xagent/agent_eval/
cases.py
suite.py
runner.py
recorder.py
evaluators.py
deterministic.py
judge.py
metrics.py
report.py
schemas.py

components/xagent/agent_experiment/
snapshot.py
proposal.py
patcher.py
comparator.py
suggestion.py
promotion.py
schemas.py

bases/xagent/agent_eval_cli/
main.py

development/eval/
suites/
local_smoke.yaml
diagnosis_regression.yaml
holdout.yaml
results/
proposals/
candidates/
reports/

agent_eval is responsible for running and scoring cases.

agent_experiment is responsible for snapshots, proposals, candidate configs, comparison, and promotion recommendations.

The existing agent_flow runtime should remain the execution engine.

4. Core design principle

Keep the loop deterministic around the LLM.

The LLM can be used for:

- qualitative judging
- failure pattern analysis
- proposal generation

But deterministic code must own:

- eval suite loading
- run execution
- config snapshotting
- metric aggregation
- patch application
- baseline/candidate comparison
- promotion gates

This prevents “LLM says it is better” from becoming the only signal.

5. Milestone plan
   Milestone 1: Offline eval runner

Implement only:

- EvalCase model
- EvalSuite model
- suite YAML loader
- run-suite CLI command
- deterministic evaluator
- run result recorder
- JSON result output
- Markdown report output

No LLM judge required in Milestone 1.

Goal:

Given an agent_flow config and an eval suite YAML,
run all cases through AgentFlowService and produce a scored result file.
Milestone 2: LLM judge evaluator

Add:

- judge prompt
- structured judge output
- LLM judge evaluator
- judge model config
- judge-result caching by run/config hash

Goal:

Evaluate qualitative answer quality using a stable rubric.
Milestone 3: Proposal generator

Add:

- failure aggregation
- ConfigChangeProposal model
- LLM-assisted suggestion engine
- proposal YAML output

Goal:

Generate reviewable prompt/config patch proposals, but do not apply them automatically to production config.
Milestone 4: Candidate experiment runner

Add:

- apply-proposal
- candidate config directory
- rerun suite on candidate
- compare baseline vs candidate
- promotion gate

Goal:

Prove whether a proposed change improves eval scores without breaking regressions.
6. Evaluation data model

Create:

components/xagent/agent_eval/schemas.py
EvalCase
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
case_id: str
query: str
tags: list[str] = Field(default_factory=list)
difficulty: Literal["smoke", "normal", "hard"] = "normal"

    case_metadata: dict[str, Any] = Field(default_factory=dict)

    reference_answer: str | None = None
    expected_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)

    judge_rubric: str | None = None
EvalSuite
class EvalSuite(BaseModel):
suite_id: str
description: str = ""
cases: list[EvalCase]

Example suite:

suite_id: diagnosis_regression
description: Basic regression cases for vehicle diagnosis agent.

cases:
- case_id: no_start_001
  query: "Vehicle has intermittent no-start after sitting overnight. What should I check?"
  tags: [diagnosis, intermittent, starting]
  difficulty: normal
  expected_facts:
    - "battery condition should be checked"
    - "starter circuit may need diagnosis"
    - "intermittent symptoms require evidence and testing"
      forbidden_claims:
    - "definitively replace the starter"
    - "repair history confirms the issue"
      judge_rubric: |
      Prefer answers that give diagnostic steps, state uncertainty, and avoid unsupported claims.
7. Run recording model

Create:

components/xagent/agent_eval/recorder.py

Each eval case should produce a recorded run:

class EvalRunRecord(BaseModel):
suite_id: str
case_id: str

    run_id: str
    status: str
    final_response: str | None = None

    config_snapshot_id: str
    config_snapshot: dict[str, Any]

    agent_state: dict[str, Any]

    latency_seconds: float | None = None
    error: str | None = None

Record the full AgentFlowState.model_dump(mode="json").

This is important because evaluation should be possible without rerunning the agent.

8. Config snapshot model

Create:

components/xagent/agent_experiment/snapshot.py

Every eval run must snapshot:

- main config YAML content
- all referenced prompt file contents
- config hash
- prompt file hashes
- git commit SHA if available
- model config
- eval suite hash
- evaluator version

Suggested model:

class PromptSnapshot(BaseModel):
path: str
sha256: str
content: str


class ConfigSnapshot(BaseModel):
snapshot_id: str
config_path: str
config_sha256: str
config_content: str
prompt_snapshots: list[PromptSnapshot] = Field(default_factory=list)
git_commit: str | None = None
metadata: dict[str, Any] = Field(default_factory=dict)

Snapshot ID should be deterministic:

sha256(config content + prompt contents + eval suite content)

Do not compare eval results unless the snapshot IDs are known.

9. Evaluator design

Create:

components/xagent/agent_eval/evaluators.py

Protocol:

class Evaluator(Protocol):
name: str

    async def evaluate(
        self,
        *,
        case: EvalCase,
        record: EvalRunRecord,
    ) -> list[MetricScore]:
        ...

Metric model:

class MetricScore(BaseModel):
name: str
score: float
passed: bool
reason: str = ""
details: dict[str, Any] = Field(default_factory=dict)

Case result:

class CaseEvaluationResult(BaseModel):
suite_id: str
case_id: str
run_id: str
scores: list[MetricScore]
overall_score: float
passed: bool
failure_modes: list[str] = Field(default_factory=list)
notes: str = ""
10. Deterministic evaluator

Create:

components/xagent/agent_eval/deterministic.py

Deterministic checks should include:

- run completed
- final response is not empty
- forbidden claims are absent
- expected facts are present, using simple case-insensitive substring initially
- no subagent timeout, unless allowed
- no unknown/skipped subagent, unless allowed
- answer length is within configured bounds

Example:

class DeterministicEvaluator:
name = "deterministic"

    async def evaluate(self, *, case: EvalCase, record: EvalRunRecord) -> list[MetricScore]:
        ...

Use simple rules first. Do not overcomplicate semantic matching in Milestone 1.

11. LLM judge evaluator

Create later:

components/xagent/agent_eval/judge.py

Judge output schema:

class JudgeMetric(BaseModel):
score: float
reason: str
confidence: float | None = None


class JudgeOutput(BaseModel):
answer_correctness: JudgeMetric
grounding_quality: JudgeMetric
diagnostic_actionability: JudgeMetric
uncertainty_handling: JudgeMetric
hallucination_risk: JudgeMetric
planner_routing_quality: JudgeMetric
overall_score: float
failure_modes: list[str] = Field(default_factory=list)
notes: str = ""

Judge prompt should include:

- user query
- final answer
- expected facts
- forbidden claims
- run trace summary
- selected subagents
- subagent outputs
- rubric

Important: the judge should not see candidate-vs-baseline labels during single-case scoring. Comparison should happen separately.

12. Failure mode taxonomy

Use fixed failure categories.

FailureMode = Literal[
"runtime_error",
"empty_answer",
"missing_expected_fact",
"forbidden_claim",
"planner_routing_failure",
"subagent_failure",
"summary_failure",
"hallucination_risk",
"weak_uncertainty_handling",
"low_actionability",
"too_verbose",
"too_short",
"unnecessary_replan",
"insufficient_replan",
]

This helps the suggestion engine propose targeted changes.

13. Proposal model

Create:

components/xagent/agent_experiment/proposal.py

Config changes must be structured.

class ConfigPatch(BaseModel):
file: str
patch_type: Literal[
"replace_text",
"append_text",
"yaml_set",
"yaml_delete",
]

    find: str | None = None
    replace: str | None = None
    text: str | None = None

    yaml_path: list[str] | None = None
    value: Any | None = None


class ConfigChangeProposal(BaseModel):
proposal_id: str
base_snapshot_id: str

    title: str
    rationale: str
    expected_effect: list[str] = Field(default_factory=list)
    affected_metrics: list[str] = Field(default_factory=list)
    affected_cases: list[str] = Field(default_factory=list)

    risk_level: Literal["low", "medium", "high"]
    patches: list[ConfigPatch]

    requires_human_review: bool = True

Do not allow arbitrary shell commands or arbitrary Python code in proposals.

14. Suggestion engine

Create:

components/xagent/agent_experiment/suggestion.py

Input:

- eval results
- failure mode summary
- config snapshot
- prompt snapshots

Output:

ConfigChangeProposal

Rules:

- proposal must be small and atomic
- prefer prompt/config changes over code changes
- do not suggest changing more than 2 files per proposal in v1
- do not propose production mutation
- do not propose disabling safety/grounding constraints
- if the problem requires new tool/data/code, create a recommendation note instead of a patch

Map failure modes to allowed patch types:

Failure mode	Allowed change
planner_routing_failure	planner prompt, subagent description
missing_expected_fact	subagent prompt, summary prompt
weak_uncertainty_handling	summary prompt
low_actionability	summary prompt
too_verbose	summary prompt
unnecessary_replan	summary prompt, max_iterations
subagent_failure	subagent prompt/config, timeout
runtime_error	engineering recommendation only
missing_tool_or_dataset	engineering recommendation only
15. Candidate patch application

Create:

components/xagent/agent_experiment/patcher.py

apply-proposal should:

1. copy base config and prompt files into candidate directory
2. apply proposal patches only inside that candidate directory
3. produce candidate manifest
4. never mutate original files

Candidate layout:

development/eval/candidates/proposal_001/
config.yaml
prompts/
agent_flow/
planner.md
summary.md
subagents/
manuals.md
repair_history.md
proposal.yaml
manifest.json

Patch safety rules:

- replace_text must find exactly one match
- append_text only appends to allowed prompt files
- yaml_set only updates allowed config paths
- yaml_delete is disabled by default unless explicitly allowed
- patch target must be under the candidate directory
16. Comparator

Create:

components/xagent/agent_experiment/comparator.py

Input:

baseline result JSON
candidate result JSON

Output:

class MetricDelta(BaseModel):
metric_name: str
baseline: float
candidate: float
delta: float


class ComparisonReport(BaseModel):
baseline_result_path: str
candidate_result_path: str

    baseline_overall_score: float
    candidate_overall_score: float
    overall_delta: float

    metric_deltas: list[MetricDelta]
    improved_cases: list[str]
    regressed_cases: list[str]

    passed_promotion_gate: bool
    recommendation: Literal["promote", "reject", "needs_review"]
    rationale: str
17. Promotion policy

Create:

components/xagent/agent_experiment/promotion.py

Config example:

promotion_policy:
min_overall_delta: 0.2
max_regressed_cases: 0
max_critical_regressed_cases: 0
required_metric_min_scores:
answer_correctness: 7.0
hallucination_risk: 8.0
required_metric_min_deltas:
answer_correctness: 0.0
grounding_quality: 0.0

For Milestone 1, use simple defaults in code.

Promotion should only produce:

recommendation: promote | reject | needs_review

Do not auto-commit, auto-merge, or auto-promote.

18. CLI design

Create:

bases/xagent/agent_eval_cli/main.py

Add script in pyproject.toml:

[project.scripts]
xagent-agent-eval = "xagent.agent_eval_cli.main:main"

Commands:

xagent-agent-eval run-suite
xagent-agent-eval evaluate
xagent-agent-eval suggest
xagent-agent-eval apply-proposal
xagent-agent-eval compare
xagent-agent-eval report
run-suite
uv run --active xagent-agent-eval run-suite \
--config development/config/agent-flow.local.yaml \
--suite development/eval/suites/local_smoke.yaml \
--output development/eval/results/local_smoke.baseline.json

Behavior:

- load AgentFlowAppConfig using existing runtime config loader
- load EvalSuite YAML
- snapshot config and prompts
- for each case, call AgentFlowService.in_memory(config).start_run(...)
- record full AgentFlowState
- run deterministic evaluator
- write EvalSuiteResult JSON
  suggest
  uv run --active xagent-agent-eval suggest \
  --result development/eval/results/local_smoke.baseline.json \
  --output development/eval/proposals/proposal_001.yaml

Milestone 1 can make this command return:

Not implemented yet

Milestone 3 implements it.

apply-proposal
uv run --active xagent-agent-eval apply-proposal \
--proposal development/eval/proposals/proposal_001.yaml \
--output-dir development/eval/candidates/proposal_001
compare
uv run --active xagent-agent-eval compare \
--baseline development/eval/results/local_smoke.baseline.json \
--candidate development/eval/results/local_smoke.proposal_001.json \
--output development/eval/reports/proposal_001.compare.md
19. Eval result output schema

Create:

class EvalSuiteResult(BaseModel):
suite_id: str
result_id: str

    config_snapshot_id: str
    config_snapshot: ConfigSnapshot

    started_at: str
    completed_at: str | None = None

    case_records: list[EvalRunRecord]
    case_evaluations: list[CaseEvaluationResult]

    overall_score: float
    passed: bool
    failure_summary: dict[str, int] = Field(default_factory=dict)

Store as JSON:

development/eval/results/<suite_id>.<label>.json
20. Reporting

Create:

components/xagent/agent_eval/report.py

Generate Markdown:

# Eval Report: local_smoke

Overall score: 7.8
Passed: true

## Case Summary

| Case | Score | Passed | Failure Modes |
|---|---:|---|---|
| no_start_001 | 8.0 | true | - |
| battery_002 | 6.5 | false | missing_expected_fact |

## Regressions

None.

## Notes

...

Reports should be human-readable and suitable for PR review.

21. Dataset split recommendation

Use three suites:

local_smoke.yaml
Very small, fast, used during development.

diagnosis_regression.yaml
Main development/optimization set.

holdout.yaml
Not used by suggestion engine. Used only for final comparison.

Do not let the suggestion engine optimize directly against holdout cases.

This is important because prompt/config optimization can overfit to a small set of judge examples.

22. Human feedback integration

Do not build a full UI in the first version.

Start with YAML feedback files:

development/eval/human_feedback/
no_start_001.feedback.yaml

Example:

case_id: no_start_001
score: 8
feedback: >
Good answer, but it should ask about battery age and cold cranking voltage.
preferred_facts:
- "ask about battery age"
- "mention cold cranking voltage"

Later, this can be converted into updated eval cases.

23. Testing plan

Add tests:

test/agent_eval/test_suite_loader.py
- loads valid suite YAML
- rejects duplicate case IDs
- rejects missing query

test/agent_eval/test_deterministic_evaluator.py
- passes expected facts
- fails forbidden claims
- fails empty answer
- records failure modes

test/agent_eval/test_runner.py
- runs fake agent_flow against local suite
- writes EvalSuiteResult
- includes config snapshot

test/agent_experiment/test_snapshot.py
- deterministic snapshot hash
- prompt files included

test/agent_experiment/test_patcher.py
- replace_text applies exactly once
- replace_text fails on no match
- replace_text fails on multiple matches
- patch cannot escape candidate directory

test/agent_experiment/test_comparator.py
- computes metric deltas
- detects regressed cases
- applies promotion policy

All tests should use fake models/providers. No external API keys.

24. Concrete Codex implementation order

Give Codex this order:

1. Add components/xagent/agent_eval/schemas.py.
2. Add EvalSuite YAML loader.
3. Add deterministic evaluator.
4. Add config/prompt snapshotter.
5. Add EvalSuiteRunner that calls AgentFlowService.in_memory(config).
6. Add run-suite CLI command.
7. Add Markdown report generator.
8. Add tests for suite loading, deterministic evaluator, runner, and snapshotter.
9. Add proposal schemas.
10. Add patcher with safe candidate directory application.
11. Add comparator and promotion policy.
12. Add tests for patcher and comparator.
13. Leave LLM judge and suggestion engine as explicit extension points or simple stubs unless time allows.
25. Codex-ready prompt
    Implement an offline evaluation and configuration-improvement loop around the existing xagent-p agent_flow runtime.

Important context:
- The repo already has components/xagent/agent_flow with config, models, runtime, service, step_runner, planner, subagents, summary, and llm_adapter.
- Do not rewrite agent_flow.
- Do not introduce LangGraph.
- Use AgentFlowService as the execution API.
- Use existing config loading patterns where possible.

Add new components:
- components/xagent/agent_eval/
- components/xagent/agent_experiment/
- bases/xagent/agent_eval_cli/
- development/eval/suites/
- development/eval/results/
- development/eval/proposals/
- development/eval/candidates/
- development/eval/reports/

Milestone 1 must implement:
1. EvalCase and EvalSuite Pydantic models.
2. YAML suite loader.
3. Deterministic evaluator.
4. Config/prompt snapshotting with SHA-256.
5. EvalSuiteRunner that runs each case through AgentFlowService.in_memory(config).
6. EvalSuiteResult JSON output.
7. Markdown report output.
8. CLI command:
   xagent-agent-eval run-suite --config ... --suite ... --output ...
9. Unit tests using fake agent_flow config only.

Milestone 2+ should add:
1. LLM judge evaluator.
2. ConfigChangeProposal schema.
3. Suggestion engine.
4. Safe proposal patcher.
5. Candidate config directories.
6. Baseline-vs-candidate comparator.
7. Promotion policy.

Important safety constraints:
- Do not let LLM suggestions directly mutate production config.
- Proposals must be structured ConfigChangeProposal objects.
- Patches must be applied only to candidate directories.
- replace_text patches must match exactly one location.
- Do not allow shell commands or arbitrary Python code in proposals.
- Do not require real LLM API keys in unit tests.
- Keep the first milestone file-based; do not add a database dependency.

Implementation style:
- Keep code simple.
- Prefer small Pydantic schemas and plain functions.
- Avoid creating a generic experiment framework.
- Make the output easy to review in PRs.
26. My final recommendation

For the next PR, only implement Milestone 1.

That gives you a solid foundation:

eval suite -> run agent -> record state -> deterministic score -> report

Once that works, the LLM-based suggestion loop becomes much safer because it will be grounded in real recorded runs and measurable evaluation results.