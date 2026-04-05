from pathlib import Path

import pytest
from pydantic import ValidationError

from xagent.config import StrictConfigModel
from xagent.config import load_typed_config


class UvicornConfig(StrictConfigModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class CorsConfig(StrictConfigModel):
    allow_origins: list[str] = []


class FastAPIConfig(StrictConfigModel):
    cors: CorsConfig = CorsConfig()


class AppConfig(StrictConfigModel):
    fastapi: FastAPIConfig = FastAPIConfig()
    uvicorn: UvicornConfig = UvicornConfig()


def test_load_typed_config_merges_files_with_later_file_precedence_and_env_map_wins(tmp_path: Path):
    first_yaml = tmp_path / "base.yaml"
    first_yaml.write_text(
        "\n".join(
            [
                "uvicorn:",
                "  host: yaml-host",
                "  port: 8100",
                "fastapi:",
                "  cors:",
                "    allow_origins:",
                "      - https://base.example.com",
            ]
        ),
        encoding="utf-8",
    )
    second_env = tmp_path / "override.env"
    second_env.write_text(
        "\n".join(
            [
                "UVICORN__PORT=9100",
                "UVICORN__RELOAD=false",
                'FASTAPI__CORS__ALLOW_ORIGINS=["https://override.example.com"]',
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(
        AppConfig,
        env_map={"UVICORN__PORT": "9300", "UVICORN__RELOAD": "true"},
        input_files=[first_yaml, second_env],
    )

    assert config.uvicorn.host == "yaml-host"
    assert config.uvicorn.port == 9300
    assert config.uvicorn.reload is True
    assert config.fastapi.cors.allow_origins == ["https://override.example.com"]


def test_load_typed_config_treats_yaml_extension_case_insensitively(tmp_path: Path):
    yaml_file = tmp_path / "CONFIG.YML"
    yaml_file.write_text(
        "\n".join(
            [
                "uvicorn:",
                "  port: 8500",
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(AppConfig, env_map=None, input_files=[yaml_file])

    assert config.uvicorn.port == 8500


def test_load_typed_config_rejects_extra_fields(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "\n".join(
            [
                "uvicorn:",
                "  port: 8500",
                "unknown_section:",
                "  enabled: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_typed_config(AppConfig, env_map=None, input_files=[yaml_file])


def test_load_typed_config_applies_type_conversion(tmp_path: Path):
    env_file = tmp_path / "config.env"
    env_file.write_text(
        "\n".join(
            [
                "UVICORN__PORT=9200",
                "UVICORN__RELOAD=true",
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(AppConfig, env_map=None, input_files=[env_file])

    assert config.uvicorn.port == 9200
    assert config.uvicorn.reload is True


def test_load_typed_config_rejects_invalid_yaml_key_names(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "\n".join(
            [
                "uvicorn__bad:",
                "  port: 8500",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="consecutive underscores"):
        load_typed_config(AppConfig, env_map=None, input_files=[yaml_file])


def test_load_typed_config_rejects_invalid_model_field_names():
    class InvalidConfig(StrictConfigModel):
        bad_name_: str = "oops"

    with pytest.raises(ValueError, match="may not end with an underscore"):
        load_typed_config(InvalidConfig, env_map=None, input_files=[])


def test_load_typed_config_rejects_case_insensitive_yaml_key_conflicts(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "\n".join(
            [
                "uvicorn:",
                "  host: localhost",
                "Uvicorn:",
                "  port: 8500",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="case-insensitively"):
        load_typed_config(AppConfig, env_map=None, input_files=[yaml_file])


def test_load_typed_config_rejects_case_insensitive_model_field_conflicts():
    class InvalidConfig(StrictConfigModel):
        foo: str = "a"
        FOO: str = "b"

    with pytest.raises(ValueError, match="case-insensitively"):
        load_typed_config(InvalidConfig, env_map=None, input_files=[])
