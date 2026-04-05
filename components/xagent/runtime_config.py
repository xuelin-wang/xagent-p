import argparse
import os
from pathlib import Path
from typing import Sequence
from typing import TypeVar

from xagent.config import StrictConfigModel
from xagent.config import load_typed_config


ConfigType = TypeVar("ConfigType", bound=StrictConfigModel)


def _require_arg_value(flag: str, value: str | None) -> str:
    if value is None or not value:
        raise argparse.ArgumentTypeError(f"{flag} requires a file path.")
    return value


def _validate_config_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix not in {".yaml", ".yml"}:
        raise argparse.ArgumentTypeError(
            f"--config expects a .yaml or .yml file, got: {path}"
        )
    return path


def _validate_env_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        raise argparse.ArgumentTypeError(
            f"--env does not accept .yaml or .yml files, got: {path}"
        )
    return path


def extract_config_file_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    input_files: list[str] = []
    remaining_args: list[str] = []
    index = 0
    args = list(argv)

    while index < len(args):
        arg = args[index]

        if arg == "--config":
            index += 1
            input_files.append(_validate_config_path(_require_arg_value("--config", args[index] if index < len(args) else None)))
        elif arg.startswith("--config="):
            input_files.append(_validate_config_path(_require_arg_value("--config", arg.split("=", 1)[1])))
        elif arg == "--env":
            index += 1
            input_files.append(_validate_env_path(_require_arg_value("--env", args[index] if index < len(args) else None)))
        elif arg.startswith("--env="):
            input_files.append(_validate_env_path(_require_arg_value("--env", arg.split("=", 1)[1])))
        else:
            remaining_args.append(arg)

        index += 1

    return input_files, remaining_args


def _filter_env_map(env_map: dict[str, str], config_type: type[ConfigType]) -> dict[str, str]:
    top_level_fields = {field_name.casefold() for field_name in config_type.model_fields}
    filtered: dict[str, str] = {}

    for key, value in env_map.items():
        first_segment = key.split("__", 1)[0].strip().casefold()
        if first_segment in top_level_fields:
            filtered[key] = value

    return filtered


def load_runtime_config(
    config_type: type[ConfigType],
    argv: Sequence[str],
) -> tuple[ConfigType, list[str]]:
    input_files, remaining_args = extract_config_file_args(argv)
    env_map = _filter_env_map(dict(os.environ), config_type)
    config = load_typed_config(config_type, env_map=env_map, input_files=input_files)
    return config, remaining_args
