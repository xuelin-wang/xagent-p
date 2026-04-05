import argparse
from pathlib import Path

import pytest

from xagent.config import StrictConfigModel
from xagent.runtime_config import extract_config_file_args
from xagent.runtime_config import load_runtime_config


class SampleCorsConfig(StrictConfigModel):
    allow_origins: list[str] = []


class SampleFastAPIConfig(StrictConfigModel):
    cors: SampleCorsConfig = SampleCorsConfig()


class SampleRuntimeConfig(StrictConfigModel):
    fastapi: SampleFastAPIConfig = SampleFastAPIConfig()
    port: int = 8000
    openai_model: str = "gpt-4.1-mini"


def test_extract_config_file_args_preserves_mixed_file_order():
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


def test_extract_config_file_args_rejects_non_yaml_config_paths():
    with pytest.raises(argparse.ArgumentTypeError, match=r"\-\-config expects"):
        extract_config_file_args(["--config", "config.env"])


def test_extract_config_file_args_rejects_yaml_env_paths():
    with pytest.raises(argparse.ArgumentTypeError, match=r"\-\-env does not accept"):
        extract_config_file_args(["--env", "config.yaml"])


def test_load_runtime_config_uses_os_environ_with_highest_precedence(monkeypatch, tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "\n".join(
            [
                "port: 7000",
                "fastapi:",
                "  cors:",
                "    allow_origins:",
                "      - https://yaml.example.com",
            ]
        ),
        encoding="utf-8",
    )
    env_file = tmp_path / "override.env"
    env_file.write_text(
        "\n".join(
            [
                "PORT=7100",
                'FASTAPI__CORS__ALLOW_ORIGINS=["https://envfile.example.com"]',
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PORT", "7200")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("UNRELATED_ENV", "ignored")

    config, remaining_args = load_runtime_config(
        SampleRuntimeConfig,
        ["--config", str(yaml_file), "--env", str(env_file), "leftover"]
    )

    assert isinstance(config, SampleRuntimeConfig)
    assert config.port == 7200
    assert config.openai_model == "gpt-test"
    assert config.fastapi.cors.allow_origins == ["https://envfile.example.com"]
    assert remaining_args == ["leftover"]
