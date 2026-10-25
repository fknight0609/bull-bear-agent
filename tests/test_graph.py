import pytest
from langgraph.graph import END

from src.graph import graph, route_after_parse
from src.nodes import dispatch as dispatch_module
from src.nodes import parse_query as parse_module
from src.state import AgentState
from src.tools.resolve_ticker import TickerResolution


def test_graph_resolves_company_and_dispatches(monkeypatch):
    monkeypatch.setattr(parse_module, "extract_companies", lambda user_query: ["Nvidia"])
    monkeypatch.setattr(dispatch_module, "choose_workers", lambda user_query, company_name, ticker: ["financials"])
    result = graph.invoke({"user_query": "What are Nvidia's margins?"})
    assert result["resolution"].ticker == "NVDA"
    assert result["mandates_dispatched"] == ["financials"]


def test_graph_skips_dispatch_when_ticker_ambiguous(monkeypatch):
    monkeypatch.setattr(parse_module, "extract_companies", lambda user_query: ["Apple"])
    result = graph.invoke({"user_query": "Is Apple a buy?"})
    assert result["resolution"].is_present == "ambiguous"
    assert "mandates_dispatched" not in result  # never written, so dispatch didn't run


@pytest.mark.parametrize(
    "resolution, question, expected",
    [
        (TickerResolution(is_present="yes", ticker="NVDA"), None, "dispatch"),
        (TickerResolution(is_present="no"), None, END),
        (TickerResolution(is_present="ambiguous", candidates=["A", "B"]), None, END),
        (TickerResolution(is_present="no"), "Which company?", END),
    ],
)
def test_route_after_parse(resolution, question, expected):
    state = AgentState(user_query="q", resolution=resolution, clarifying_question=question)
    assert route_after_parse(state) == expected
