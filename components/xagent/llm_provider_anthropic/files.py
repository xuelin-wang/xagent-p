ANTHROPIC_FILES_BETA = "files-api-2025-04-14"


def anthropic_files_beta_header() -> dict[str, str]:
    return {"anthropic-beta": ANTHROPIC_FILES_BETA}
