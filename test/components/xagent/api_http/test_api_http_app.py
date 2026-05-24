import httpx
from fastapi.testclient import TestClient
from openai import AuthenticationError
from pytest import MonkeyPatch

import xagent.api_http.app as api_http_app
from xagent.agent_flow.config import AgentFlowAppConfig, SubagentConfig
from xagent.api_http.app import ApiHttpConfig, create_app


def test_health_endpoint_exists() -> None:
    app = create_app()
    routes = {getattr(route, "path", None) for route in app.routes}
    assert "/healthz" in routes
    assert "/query" in routes
    assert "/agent-flow/runs" in routes
    assert "/agent-flow/runs/{run_id}" in routes
    assert "/agent-flow/runs/{run_id}/resume" in routes
    assert "/agent-flow/runs/{run_id}/input" in routes


def test_query_returns_502_when_openai_authentication_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    def raise_authentication_error(_config: ApiHttpConfig) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
        response = httpx.Response(401, request=request)
        raise AuthenticationError(
            "Incorrect API key provided.",
            response=response,
            body={"error": {"code": "invalid_api_key"}},
        )

    monkeypatch.setattr(api_http_app, "_build_runtime", raise_authentication_error)

    client = TestClient(create_app())
    response = client.post("/query", json={"query": "test query"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "OpenAI authentication failed. Check the configured API key before "
            "retrying the query."
        )
    }


def test_agent_flow_routes_start_get_and_resume_run() -> None:
    client = TestClient(create_app(_agent_flow_api_config()))

    start_response = client.post(
        "/agent-flow/runs",
        json={
            "query": "diagnose no start",
            "case_id": "case_123",
            "metadata": {"vehicle": "example"},
        },
    )

    assert start_response.status_code == 200
    started = start_response.json()
    assert started["status"] == "completed"
    assert started["case_id"] == "case_123"
    assert started["metadata"] == {"vehicle": "example"}
    assert started["final_response"] == (
        "manuals handled query 'diagnose no start' for iteration 0."
    )

    get_response = client.get(f"/agent-flow/runs/{started['run_id']}")
    assert get_response.status_code == 200
    assert get_response.json() == started

    resume_response = client.post(f"/agent-flow/runs/{started['run_id']}/resume")
    assert resume_response.status_code == 200
    assert resume_response.json() == started


def test_agent_flow_routes_return_404_for_missing_run() -> None:
    client = TestClient(create_app(_agent_flow_api_config()))

    get_response = client.get("/agent-flow/runs/missing")
    resume_response = client.post("/agent-flow/runs/missing/resume")
    input_response = client.post(
        "/agent-flow/runs/missing/input", json={"content": "hello"}
    )

    assert get_response.status_code == 404
    assert get_response.json() == {"detail": "Agent flow run not found."}
    assert resume_response.status_code == 404
    assert resume_response.json() == {"detail": "Agent flow run not found."}
    assert input_response.status_code == 404
    assert input_response.json() == {"detail": "Agent flow run not found."}


def test_agent_flow_input_returns_409_for_non_waiting_run() -> None:
    client = TestClient(create_app(_agent_flow_api_config()))

    start_response = client.post(
        "/agent-flow/runs",
        json={"query": "diagnose no start"},
    )
    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]

    input_response = client.post(
        f"/agent-flow/runs/{run_id}/input", json={"content": "some input"}
    )

    assert input_response.status_code == 409


def _agent_flow_api_config() -> ApiHttpConfig:
    return ApiHttpConfig(
        agent_flow=AgentFlowAppConfig(
            subagents={
                "manuals": SubagentConfig(
                    name="manuals",
                    description="Search service manuals.",
                    prompt_template="prompts/agent_flow/subagents/manuals.md",
                )
            }
        )
    )
