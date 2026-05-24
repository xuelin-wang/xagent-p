from pathlib import Path

import pytest
from pydantic import ValidationError

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.config import load_typed_config


def test_agent_flow_config_loads_strict_nested_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "agent-flow.yaml"
    config_file.write_text(
        "\n".join(
            [
                "workflow:",
                "  name: diagnosis_agent_flow",
                "  max_iterations: 2",
                "execution_policy:",
                "  default_step_policy:",
                "    timeout_ms: 1000",
                "    deadline_ms: 5000",
                "  step_overrides:",
                "    planner:",
                "      timeout_ms: 2000",
                "planner:",
                "  model: planner_model",
                "subagents:",
                "  manuals:",
                "    name: manuals",
                "    description: Search service manuals.",
                "    prompt_template: prompts/agent_flow/subagents/manuals.md",
                "    tools:",
                "      - manual_search",
                "models:",
                "  planner_model:",
                "    provider: fake",
                "    model: fake-planner",
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(
        AgentFlowAppConfig,
        env_map=None,
        input_files=[config_file],
    )

    assert config.workflow.name == "diagnosis_agent_flow"
    assert config.workflow.max_iterations == 2
    assert config.execution_policy.default_step_policy.timeout_ms == 1000
    assert config.execution_policy.default_step_policy.deadline_ms == 5000
    assert config.execution_policy.step_overrides["planner"].timeout_ms == 2000
    assert config.planner.model == "planner_model"
    assert config.subagents["manuals"].tools == ["manual_search"]
    assert config.models["planner_model"].model == "fake-planner"


def test_agent_flow_config_rejects_unknown_fields(tmp_path: Path) -> None:
    config_file = tmp_path / "agent-flow.yaml"
    config_file.write_text(
        "\n".join(
            [
                "workflow:",
                "  max_iterations: 2",
                "unexpected: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_typed_config(
            AgentFlowAppConfig,
            env_map=None,
            input_files=[config_file],
        )


def test_agent_flow_config_rejects_negative_timeout(tmp_path: Path) -> None:
    config_file = tmp_path / "agent-flow.yaml"
    config_file.write_text(
        "\n".join(
            [
                "execution_policy:",
                "  default_step_policy:",
                "    timeout_ms: -1",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_typed_config(
            AgentFlowAppConfig,
            env_map=None,
            input_files=[config_file],
        )
