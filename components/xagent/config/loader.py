from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml

from xagent.config.strict import (
    StrictConfigModel,
    _validate_config_key_name,
    merge_dicts_recursive,
    validate_mapping_key_names,
    validate_model_key_names,
)

ConfigType = TypeVar("ConfigType", bound=StrictConfigModel)


def _parse_env_value(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def _assign_nested_value(target: dict[str, Any], key: str, value: Any) -> None:
    raw_parts = key.split("__")
    if any(not part.strip() for part in raw_parts):
        raise ValueError(
            f"Invalid environment key '{key}': empty path segments are not allowed."
        )

    parts = [part.strip().lower() for part in raw_parts]
    for part in parts:
        _validate_config_key_name(part)

    current = target
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def parse_env_mapping(env: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, raw_value in env.items():
        _assign_nested_value(parsed, key, _parse_env_value(raw_value))
    return parsed


def parse_env_file(path: str | Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        _assign_nested_value(parsed, key.strip(), _parse_env_value(value.strip()))
    return parsed


def parse_yaml_file(path: str | Path) -> dict[str, Any]:
    loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML file must contain a top-level mapping: {path}")
    validate_mapping_key_names(loaded)
    return loaded


def load_typed_config(
    config_type: type[ConfigType],
    env_map: dict[str, str] | None,
    input_files: list[str | Path],
) -> ConfigType:
    validate_model_key_names(config_type)
    merged: dict[str, Any] = {}

    for input_file in input_files:
        path = Path(input_file)
        suffix = path.suffix.lower()
        parsed = (
            parse_yaml_file(path)
            if suffix in {".yaml", ".yml"}
            else parse_env_file(path)
        )
        merged = merge_dicts_recursive(merged, parsed)

    if env_map:
        merged = merge_dicts_recursive(merged, parse_env_mapping(env_map))

    return config_type.model_validate(merged)
