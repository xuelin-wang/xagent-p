import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_openai import ChatOpenAI
from openai import AuthenticationError
from pydantic import BaseModel, Field, SecretStr

from xagent.agent_flow.config import AgentFlowAppConfig
from xagent.agent_flow.service import AgentFlowService
from xagent.api_http.routes_agent_flow import create_agent_flow_router
from xagent.config import StrictConfigModel
from xagent.langchain_agents.app import LangChainMultiAgentApp
from xagent.langchain_agents.corpus import build_sample_documents
from xagent.langchain_agents.merge import LangChainResponseMerger
from xagent.langchain_agents.planner import LangChainPlanner
from xagent.langchain_agents.subagents import RAGSubagent
from xagent.runtime_config import load_runtime_config


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, description="User query to answer.")


class QueryResponse(BaseModel):
    reply: str
    subagent_statuses: list[str]


class CorsConfig(StrictConfigModel):
    allow_origins: list[str] = Field(default_factory=list)


class FastAPIConfig(StrictConfigModel):
    cors: CorsConfig = CorsConfig()


class ApiHttpConfig(StrictConfigModel):
    fastapi: FastAPIConfig = FastAPIConfig()
    agent_flow: AgentFlowAppConfig = AgentFlowAppConfig()
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    xagent_max_wait_seconds: float = 10.0
    openai_api_key: SecretStr | None = Field(
        default=None,
        json_schema_extra={"secret": True, "env_var": "OPENAI_API_KEY"},
    )


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
        env_cfg = os.environ.get("XAGENT_API_HTTP_CONFIG")
        argv = ["--config", env_cfg] if env_cfg else []
        config, _ = load_runtime_config(ApiHttpConfig, argv)
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

    app.include_router(
        create_agent_flow_router(AgentFlowService.in_memory(config.agent_flow))
    )

    _demo_dir = Path(__file__).parent / "static" / "demo"
    if _demo_dir.exists():
        app.mount("/demo", StaticFiles(directory=_demo_dir, html=True), name="demo")

    return app


app = create_app()
