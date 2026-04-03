from langchain_core.documents import Document


def build_sample_documents() -> list[Document]:
    return [
        Document(
            id="polylith-overview",
            page_content=(
                "Polylith organizes a codebase into small reusable bricks such as "
                "components and bases, then composes them into projects."
            ),
            metadata={
                "title": "Polylith Overview",
                "topic": "architecture",
                "source": "sample-corpus",
            },
        ),
        Document(
            id="planner-pattern",
            page_content=(
                "A supervisor agent can plan work, route tasks to specialist "
                "subagents in parallel, wait for their results, and merge them into "
                "one response."
            ),
            metadata={
                "title": "Supervisor Pattern",
                "topic": "agents",
                "source": "sample-corpus",
            },
        ),
        Document(
            id="rag-pattern",
            page_content=(
                "A RAG agent retrieves semantically similar documents, uses the "
                "retrieved context as grounded evidence, and answers with citations "
                "or source references."
            ),
            metadata={
                "title": "RAG Pattern",
                "topic": "retrieval",
                "source": "sample-corpus",
            },
        ),
        Document(
            id="langchain-shared-models",
            page_content=(
                "When building multiple agent flavors in one repository, keep shared "
                "request and response models framework-neutral, and isolate framework "
                "specific orchestration code behind thin adapters."
            ),
            metadata={
                "title": "Shared Agent Models",
                "topic": "architecture",
                "source": "sample-corpus",
            },
        ),
    ]
