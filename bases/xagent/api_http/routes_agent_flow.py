from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from xagent.agent_flow.models import AgentFlowState
from xagent.agent_flow.service import AgentFlowService


class AgentFlowRunRequest(BaseModel):
    query: str = Field(min_length=1, description="User query to answer.")
    case_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class AgentFlowUserInputRequest(BaseModel):
    content: str = Field(min_length=1)


def create_agent_flow_router(service: AgentFlowService) -> APIRouter:
    router = APIRouter(prefix="/agent-flow", tags=["agent-flow"])

    @router.post("/runs", response_model=AgentFlowState)
    async def start_run(request: AgentFlowRunRequest) -> AgentFlowState:
        return await service.start_run(
            user_query=request.query,
            case_id=request.case_id,
            metadata=request.metadata,
        )

    @router.get("/runs/{run_id}", response_model=AgentFlowState)
    async def get_run(run_id: str) -> AgentFlowState:
        try:
            return await service.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="Agent flow run not found."
            ) from exc

    @router.post("/runs/{run_id}/resume", response_model=AgentFlowState)
    async def resume_run(run_id: str) -> AgentFlowState:
        try:
            return await service.resume_run(run_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="Agent flow run not found."
            ) from exc

    @router.post("/runs/{run_id}/input", response_model=AgentFlowState)
    async def submit_user_input(
        run_id: str, request: AgentFlowUserInputRequest
    ) -> AgentFlowState:
        try:
            return await service.submit_user_input(run_id, request.content)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="Agent flow run not found."
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
