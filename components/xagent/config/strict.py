from __future__ import annotations

import re
from typing import Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_ENV_VAR_NAME_RE = re.compile(r"[A-Z][A-Z0-9_]*")


def _validate_config_key_name(name: str) -> None:
    if "__" in name:
        raise ValueError(
            f"Invalid config key '{name}': consecutive underscores are not allowed."
        )
    if name.endswith("_"):
        raise ValueError(
            f"Invalid config key '{name}': keys may not end with an underscore."
        )


def _validate_env_var_name(name: str) -> None:
    if not name:
        raise ValueError("Invalid env var name: value must not be empty.")
    if not _ENV_VAR_NAME_RE.fullmatch(name):
        raise ValueError(
            "Invalid env var name "
            f"'{name}': names must use uppercase letters, digits, and underscores."
        )


def _iter_nested_model_types(annotation: Any) -> list[type[StrictConfigModel]]:
    if isinstance(annotation, type) and issubclass(annotation, StrictConfigModel):
        return [annotation]

    origin = get_origin(annotation)
    if origin is None:
        return []

    nested: list[type[StrictConfigModel]] = []
    for arg in get_args(annotation):
        nested.extend(_iter_nested_model_types(arg))
    return nested


def validate_model_key_names(model_type: type[StrictConfigModel]) -> None:
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


def collect_model_env_var_paths(
    model_type: type[StrictConfigModel],
) -> dict[str, tuple[str, ...]]:
    visited: set[type[StrictConfigModel]] = set()
    env_var_paths: dict[str, tuple[str, ...]] = {}

    def _walk(
        current_model: type[StrictConfigModel], prefix: tuple[str, ...]
    ) -> None:
        if current_model in visited:
            return
        visited.add(current_model)

        for field_name, field_info in current_model.model_fields.items():
            extra = field_info.json_schema_extra
            if extra is not None and not isinstance(extra, dict):
                raise ValueError(
                    "Invalid config model: json_schema_extra must be a mapping "
                    f"for field '{current_model.__name__}.{field_name}'."
                )

            if extra:
                secret = extra.get("secret")
                env_var = extra.get("env_var")
                if env_var is None:
                    continue
                if secret is not True:
                    raise ValueError(
                        "Invalid config model: fields with env_var metadata must "
                        f"also set secret=True for field "
                        f"'{current_model.__name__}.{field_name}'."
                    )
                if not isinstance(env_var, str):
                    raise ValueError(
                        "Invalid config model: env_var metadata must be a string "
                        f"for field '{current_model.__name__}.{field_name}'."
                    )
                _validate_env_var_name(env_var)
                path = (*prefix, field_name)
                existing = env_var_paths.get(env_var)
                if existing is not None and existing != path:
                    raise ValueError(
                        "Invalid config model: env_var metadata must be unique "
                        f"across fields. '{env_var}' is used by "
                        f"'{'.'.join(existing)}' and '{'.'.join(path)}'."
                    )
                env_var_paths[env_var] = path

            for nested_model in _iter_nested_model_types(field_info.annotation):
                _walk(nested_model, (*prefix, field_name))

    _walk(model_type, ())
    return env_var_paths


def validate_mapping_key_names(data: Any) -> None:
    if not isinstance(data, dict):
        return

    seen_casefolded: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError(
                f"Configuration keys must be strings, got: {type(key).__name__}"
            )
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


def merge_dicts_recursive(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge_dicts_recursive(result[key], value)
        else:
            result[key] = value
    return result
