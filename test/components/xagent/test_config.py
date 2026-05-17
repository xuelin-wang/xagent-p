from pathlib import Path

import pytest
from pydantic import Field, SecretStr, ValidationError

from xagent.config import StrictConfigModel, load_typed_config


class UvicornConfig(StrictConfigModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class CorsConfig(StrictConfigModel):
    allow_origins: list[str] = Field(default_factory=list)


class FastAPIConfig(StrictConfigModel):
    cors: CorsConfig = CorsConfig()


class CredentialsConfig(StrictConfigModel):
    api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True, "env_var": "APP_API_KEY"},
    )


class AppConfig(StrictConfigModel):
    fastapi: FastAPIConfig = FastAPIConfig()
    uvicorn: UvicornConfig = UvicornConfig()
    credentials: CredentialsConfig = CredentialsConfig()


def test_load_typed_config_merges_files_with_later_file_precedence_and_env_map_wins(
    tmp_path: Path,
) -> None:
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
                "credentials:",
                "  api_key: yaml-secret",
            ]
        ),
        encoding="utf-8",
    )
    second_env = tmp_path / "override.env"
    second_env.write_text(
        "\n".join(
            [
                "APP_API_KEY=file-secret",
                "UNRELATED_ENV_FILE=ignored",
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(
        AppConfig,
        env_map={"APP_API_KEY": "env-secret", "UNRELATED_ENV": "ignored"},
        input_files=[first_yaml, second_env],
    )

    assert config.uvicorn.host == "yaml-host"
    assert config.uvicorn.port == 8100
    assert config.uvicorn.reload is False
    assert config.fastapi.cors.allow_origins == ["https://base.example.com"]
    assert config.credentials.api_key is not None
    assert config.credentials.api_key.get_secret_value() == "env-secret"


def test_load_typed_config_treats_yaml_extension_case_insensitively(
    tmp_path: Path,
) -> None:
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


def test_load_typed_config_rejects_extra_fields(tmp_path: Path) -> None:
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


def test_load_typed_config_applies_env_file_override(tmp_path: Path) -> None:
    env_file = tmp_path / "config.env"
    env_file.write_text(
        "\n".join(
            [
                "APP_API_KEY=envfile-secret",
            ]
        ),
        encoding="utf-8",
    )

    config = load_typed_config(AppConfig, env_map=None, input_files=[env_file])

    assert config.credentials.api_key is not None
    assert config.credentials.api_key.get_secret_value() == "envfile-secret"


def test_load_typed_config_rejects_invalid_yaml_key_names(
    tmp_path: Path,
) -> None:
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


def test_load_typed_config_rejects_invalid_model_field_names() -> None:
    class InvalidConfig(StrictConfigModel):
        bad_name_: str = "oops"

    with pytest.raises(ValueError, match="may not end with an underscore"):
        load_typed_config(InvalidConfig, env_map=None, input_files=[])


def test_load_typed_config_rejects_invalid_env_var_metadata() -> None:
    class InvalidConfig(StrictConfigModel):
        api_key: SecretStr | None = Field(
            default=None,
            json_schema_extra={"secret": True, "env_var": "bad_name"},
        )

    with pytest.raises(ValueError, match="Invalid env var name"):
        load_typed_config(InvalidConfig, env_map=None, input_files=[])


def test_load_typed_config_rejects_case_insensitive_yaml_key_conflicts(
    tmp_path: Path,
) -> None:
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


def test_load_typed_config_rejects_case_insensitive_model_field_conflicts() -> None:
    class InvalidConfig(StrictConfigModel):
        foo: str = "a"
        FOO: str = "b"

    with pytest.raises(ValueError, match="case-insensitively"):
        load_typed_config(InvalidConfig, env_map=None, input_files=[])
