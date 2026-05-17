from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml

from xagent.config.strict import (
    StrictConfigModel,
    collect_model_env_var_paths,
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


def _assign_path_value(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for part in path[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[path[-1]] = value


def parse_env_mapping(env: dict[str, str]) -> dict[str, Any]:
    return {key: _parse_env_value(raw_value) for key, raw_value in env.items()}


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
        parsed[key.strip()] = _parse_env_value(value.strip())
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
    env_var_paths = collect_model_env_var_paths(config_type)
    merged: dict[str, Any] = {}

    for input_file in input_files:
        input_path = Path(input_file)
        suffix = input_path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            merged = merge_dicts_recursive(merged, parse_yaml_file(input_path))
            continue

        parsed_env = parse_env_file(input_path)
        for env_var, raw_value in parsed_env.items():
            field_path = env_var_paths.get(env_var)
            if field_path is None:
                continue
            _assign_path_value(merged, field_path, raw_value)

    if env_map:
        for env_var, raw_value in parse_env_mapping(env_map).items():
            field_path = env_var_paths.get(env_var)
            if field_path is None:
                continue
            _assign_path_value(merged, field_path, raw_value)

    return config_type.model_validate(merged)
