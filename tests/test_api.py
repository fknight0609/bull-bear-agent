"""API tests: graph.invoke is monkeypatched, so no Gemini or network calls."""

import pytest
from fastapi.testclient import TestClient

from api.index import app
from src.graph import graph

API_KEY = "test-key"
client = TestClient(app, headers={"X-API-Key": API_KEY})
anonymous = TestClient(app)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", API_KEY)


def _fake_state(query: str) -> dict:
    return {"user_query": query, "clarifying_question": "Which company?"}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_research_returns_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph, "invoke", lambda state: _fake_state(state["user_query"]))
    response = client.post("/research", json={"query": "  Nvidia margins?  "})
    assert response.status_code == 200
    body = response.json()
    assert body["user_query"] == "Nvidia margins?"  # stripped
    assert body["clarifying_question"] == "Which company?"
    assert {"company_name", "resolution", "mandates_dispatched", "findings", "thesis"} <= body.keys()


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_rejected(query: str) -> None:
    assert client.post("/research", json={"query": query}).status_code == 422


def test_overlong_query_rejected() -> None:
    assert client.post("/research", json={"query": "x" * 501}).status_code == 422


def test_graph_exception_hides_details(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(state: dict) -> dict:
        raise RuntimeError("secret-api-key-leak")

    monkeypatch.setattr(graph, "invoke", boom)
    response = client.post("/research", json={"query": "Nvidia"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Research failed"}
    assert "secret-api-key-leak" not in response.text


def test_expose_errors_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(state: dict) -> dict:
        raise RuntimeError("visible-when-enabled")

    monkeypatch.setattr(graph, "invoke", boom)
    monkeypatch.setenv("EXPOSE_ERRORS", "1")
    response = client.post("/research", json={"query": "Nvidia"})
    assert response.status_code == 500
    assert response.json()["error"] == "RuntimeError: visible-when-enabled"


def test_research_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    called = []
    monkeypatch.setattr(graph, "invoke", lambda state: called.append(state) or _fake_state(state["user_query"]))
    assert anonymous.post("/research", json={"query": "Nvidia"}).status_code == 401
    wrong = anonymous.post("/research", json={"query": "Nvidia"}, headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401
    assert wrong.json() == {"detail": "Invalid or missing API key"}
    assert called == []  # the graph (and Gemini) is never reached without the key


def test_research_fails_closed_when_key_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.post("/research", json={"query": "Nvidia"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Service not configured"}


def test_health_needs_no_key() -> None:
    assert anonymous.get("/health").status_code == 200
