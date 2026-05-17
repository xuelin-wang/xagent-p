import argparse
from pathlib import Path

import pytest
from pydantic import Field, SecretStr
from pytest import MonkeyPatch

from xagent.config import StrictConfigModel
from xagent.runtime_config import extract_config_file_args, load_runtime_config


class SampleCorsConfig(StrictConfigModel):
    allow_origins: list[str] = Field(default_factory=list)


class SampleFastAPIConfig(StrictConfigModel):
    cors: SampleCorsConfig = SampleCorsConfig()


class SampleRuntimeConfig(StrictConfigModel):
    port: int = 8000
    fastapi: SampleFastAPIConfig = SampleFastAPIConfig()
    openai_api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True, "env_var": "OPENAI_API_KEY"},
    )


def test_extract_config_file_args_preserves_mixed_file_order() -> None:
    input_files, remaining_args = extract_config_file_args(
        [
            "--config",
            "base.yaml",
            "--env",
            "dev.env",
            "query text",
            "--config=override.yml",
            "--show-plan",
        ]
    )

    assert input_files == ["base.yaml", "dev.env", "override.yml"]
    assert remaining_args == ["query text", "--show-plan"]


def test_extract_config_file_args_rejects_non_yaml_config_paths() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"\-\-config expects"):
        extract_config_file_args(["--config", "config.env"])


def test_extract_config_file_args_rejects_yaml_env_paths() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"\-\-env does not accept"):
        extract_config_file_args(["--env", "config.yaml"])


def test_load_runtime_config_uses_os_environ_with_highest_precedence(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "\n".join(
            [
                "port: 7000",
                "fastapi:",
                "  cors:",
                "    allow_origins:",
                "      - https://yaml.example.com",
                "openai_api_key: yaml-secret",
            ]
        ),
        encoding="utf-8",
    )
    env_file = tmp_path / "override.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=envfile-secret",
                "UNRELATED_ENV_FILE=ignored",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    monkeypatch.setenv("UNRELATED_ENV", "ignored")

    config, remaining_args = load_runtime_config(
        SampleRuntimeConfig,
        ["--config", str(yaml_file), "--env", str(env_file), "leftover"],
    )

    assert isinstance(config, SampleRuntimeConfig)
    assert config.port == 7000
    assert config.fastapi.cors.allow_origins == ["https://yaml.example.com"]
    assert config.openai_api_key is not None
    assert config.openai_api_key.get_secret_value() == "env-secret"
    assert remaining_args == ["leftover"]
