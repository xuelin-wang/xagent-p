import os

from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from openai import AuthenticationError

from xagent.langchain_agents.app import LangChainMultiAgentApp
from xagent.langchain_agents.corpus import build_sample_documents
from xagent.langchain_agents.merge import LangChainResponseMerger
from xagent.langchain_agents.planner import LangChainPlanner
from xagent.langchain_agents.subagents import RAGSubagent


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, description="User query to answer.")


class QueryResponse(BaseModel):
    reply: str
    subagent_statuses: list[str]


def _raise_provider_auth_error(exc: AuthenticationError) -> None:
    raise HTTPException(
        status_code=502,
        detail=(
            "OpenAI authentication failed. Check the configured API key before "
            "retrying the query."
        ),
    ) from exc


def _build_runtime() -> LangChainMultiAgentApp:
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    embedding_model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    max_wait_seconds = float(os.environ.get("XAGENT_MAX_WAIT_SECONDS", "10"))

    planner_model = ChatOpenAI(model=model_name, temperature=0)
    merger_model = ChatOpenAI(model=model_name, temperature=0.2)
    rag_subagent = RAGSubagent(
        answer_model=ChatOpenAI(model=model_name, temperature=0),
        documents=build_sample_documents(),
        embedding_model=embedding_model,
    )
    subagents = {rag_subagent.name: rag_subagent}
    return LangChainMultiAgentApp(
        planner=LangChainPlanner(planner_model, subagents),
        merger=LangChainResponseMerger(merger_model),
        subagents=subagents,
        max_wait_seconds=max_wait_seconds,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="xagent LangChain Service", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse:
        try:
            runner = _build_runtime()
            result = await runner.arun(request.query)
        except AuthenticationError as exc:
            _raise_provider_auth_error(exc)
        return QueryResponse(
            reply=result.final_reply,
            subagent_statuses=[
                f"{reply.name}:{reply.status}" for reply in result.subagent_replies
            ],
        )

    return app


app = create_app()
