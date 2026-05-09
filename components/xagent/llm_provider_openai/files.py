from xagent.llm_files import FilePurpose


def openai_file_purpose(purpose: FilePurpose) -> str:
    if purpose == FilePurpose.BATCH_INPUT:
        return "batch"
    return "user_data"
