import httpx
from fastapi.testclient import TestClient
from openai import AuthenticationError

import xagent.api_http.app as api_http_app
from xagent.api_http.app import create_app


def test_health_endpoint_exists():
    app = create_app()
    routes = {route.path for route in app.routes}
    assert "/healthz" in routes
    assert "/query" in routes


def test_query_returns_502_when_openai_authentication_fails(monkeypatch):
    def raise_authentication_error(_config):
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
