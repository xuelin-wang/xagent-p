import json
from pathlib import Path
from typing import Any
from typing import TypeVar
from typing import get_args
from typing import get_origin

import yaml
from pydantic import BaseModel
from pydantic import ConfigDict


ConfigType = TypeVar("ConfigType", bound="StrictConfigModel")


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_config_key_name(name: str) -> None:
    if "__" in name:
        raise ValueError(
            f"Invalid config key '{name}': consecutive underscores are not allowed."
        )
    if name.endswith("_"):
        raise ValueError(
            f"Invalid config key '{name}': keys may not end with an underscore."
        )


def _iter_nested_model_types(annotation: Any) -> list[type["StrictConfigModel"]]:
    if isinstance(annotation, type) and issubclass(annotation, StrictConfigModel):
        return [annotation]

    origin = get_origin(annotation)
    if origin is None:
        return []

    nested: list[type[StrictConfigModel]] = []
    for arg in get_args(annotation):
        nested.extend(_iter_nested_model_types(arg))
    return nested


def validate_model_key_names(model_type: type["StrictConfigModel"]) -> None:
    visited: set[type[StrictConfigModel]] = set()

    def _walk(current_model: type[StrictConfigModel]) -> None:
        if current_model in visited:
            return
        visited.add(current_model)

        seen_casefolded: dict[str, str] = {}
        for field_name, field_info in current_model.model_fields.items():
            _validate_config_key_name(field_name)
            normalized = field_name.casefold()
            existing = seen_casefolded.get(normalized)
            if existing is not None and existing != field_name:
                raise ValueError(
                    "Invalid config model: field names must not conflict "
                    f"case-insensitively: '{existing}' vs '{field_name}'."
                )
            seen_casefolded[normalized] = field_name
            for nested_model in _iter_nested_model_types(field_info.annotation):
                _walk(nested_model)

    _walk(model_type)


def validate_mapping_key_names(data: Any) -> None:
    if not isinstance(data, dict):
        return

    seen_casefolded: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError(f"Configuration keys must be strings, got: {type(key).__name__}")
        _validate_config_key_name(key)
        normalized = key.casefold()
        existing = seen_casefolded.get(normalized)
        if existing is not None and existing != key:
            raise ValueError(
                "Invalid configuration mapping: keys must not conflict "
                f"case-insensitively: '{existing}' vs '{key}'."
            )
        seen_casefolded[normalized] = key
        validate_mapping_key_names(value)


def merge_dicts_recursive(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge_dicts_recursive(result[key], value)
        else:
            result[key] = value
    return result


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
        parsed = parse_yaml_file(path) if suffix in {".yaml", ".yml"} else parse_env_file(path)
        merged = merge_dicts_recursive(merged, parsed)

    if env_map:
        merged = merge_dicts_recursive(merged, parse_env_mapping(env_map))

    return config_type.model_validate(merged)
