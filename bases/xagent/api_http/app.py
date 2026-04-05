from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from openai import AuthenticationError

from xagent.langchain_agents.app import LangChainMultiAgentApp
from xagent.langchain_agents.corpus import build_sample_documents
from xagent.langchain_agents.merge import LangChainResponseMerger
from xagent.langchain_agents.planner import LangChainPlanner
from xagent.langchain_agents.subagents import RAGSubagent
from xagent.config import StrictConfigModel
from xagent.runtime_config import load_runtime_config


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, description="User query to answer.")


class QueryResponse(BaseModel):
    reply: str
    subagent_statuses: list[str]


class CorsConfig(StrictConfigModel):
    allow_origins: list[str] = []


class FastAPIConfig(StrictConfigModel):
    cors: CorsConfig = CorsConfig()


class ApiHttpConfig(StrictConfigModel):
    fastapi: FastAPIConfig = FastAPIConfig()
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    xagent_max_wait_seconds: float = 10.0
    openai_api_key: str | None = None


def _raise_provider_auth_error(exc: AuthenticationError) -> None:
    raise HTTPException(
        status_code=502,
        detail=(
            "OpenAI authentication failed. Check the configured API key before "
            "retrying the query."
        ),
    ) from exc


def _build_runtime(config: ApiHttpConfig) -> LangChainMultiAgentApp:
    planner_model = ChatOpenAI(
        model=config.openai_model,
        temperature=0,
        api_key=config.openai_api_key,
    )
    merger_model = ChatOpenAI(
        model=config.openai_model,
        temperature=0.2,
        api_key=config.openai_api_key,
    )
    rag_subagent = RAGSubagent(
        answer_model=ChatOpenAI(
            model=config.openai_model,
            temperature=0,
            api_key=config.openai_api_key,
        ),
        documents=build_sample_documents(),
        embedding_model=config.openai_embedding_model,
        api_key=config.openai_api_key,
    )
    subagents = {rag_subagent.name: rag_subagent}
    return LangChainMultiAgentApp(
        planner=LangChainPlanner(planner_model, subagents),
        merger=LangChainResponseMerger(merger_model),
        subagents=subagents,
        max_wait_seconds=config.xagent_max_wait_seconds,
    )


def create_app(config: ApiHttpConfig | None = None) -> FastAPI:
    if config is None:
        config, _ = load_runtime_config(ApiHttpConfig, [])
    app = FastAPI(title="xagent LangChain Service", version="0.1.0")
    if config.fastapi.cors.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.fastapi.cors.allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse:
        try:
            runner = _build_runtime(config)
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
