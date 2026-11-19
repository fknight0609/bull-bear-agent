"""API tests: graph.invoke is monkeypatched, so no Gemini or network calls."""

import pytest
from fastapi.testclient import TestClient

from api.index import app
from src.graph import graph

client = TestClient(app)


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

