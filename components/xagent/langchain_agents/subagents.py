from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings


class Subagent(Protocol):
    name: str
    description: str

    async def ainvoke(self, query: str) -> str:
        ...


@dataclass(slots=True)
class RAGSubagent:
    answer_model: Any
    documents: list[Document]
    embedding_model: str = "text-embedding-3-small"
    name: str = "rag_researcher"
    description: str = (
        "Retrieves semantically similar documents and answers with grounded context."
    )
    top_k: int = 3
    _vector_store: InMemoryVectorStore = field(init=False, repr=False)
    _chain: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        embeddings = OpenAIEmbeddings(model=self.embedding_model)
        self._vector_store = InMemoryVectorStore(embeddings)
        self._vector_store.add_documents(self.documents)
        self._chain = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a retrieval-augmented specialist. Answer using only the "
                        "retrieved context. If the context is insufficient, say so clearly. "
                        "Mention the source titles you used."
                    ),
                ),
                (
                    "human",
                    "User query:\n{query}\n\nRetrieved context:\n{context}",
                ),
            ]
        ) | self.answer_model

    async def ainvoke(self, query: str) -> str:
        matches = await self._vector_store.asimilarity_search_with_score(
            query,
            k=self.top_k,
        )
        if not matches:
            return "No supporting documents were retrieved for this query."

        context = "\n\n".join(
            self._format_match(document, score) for document, score in matches
        )
        response = await self._chain.ainvoke({"query": query, "context": context})
        content = response.content if isinstance(response, AIMessage) else str(response)
        return (
            f"Retrieved {len(matches)} supporting document(s).\n"
            f"{content}"
        )

    @staticmethod
    def _format_match(document: Document, score: float) -> str:
        title = document.metadata.get("title", document.id or "Untitled")
        return (
            f"Title: {title}\n"
            f"Similarity: {score:.3f}\n"
            f"Content: {document.page_content}"
        )
