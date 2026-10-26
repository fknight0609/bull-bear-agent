import pytest
from langgraph.graph import END

from src.graph import graph, route_after_dispatch, route_after_parse
from src.nodes import dispatch as dispatch_module
from src.nodes import financials as financials_module
from src.nodes import parse_query as parse_module
from src.nodes import price_history as price_history_module
from src.nodes import sector_performance as sector_performance_module
from src.state import AgentState
from tests.test_workers import FUNDAMENTALS, PRICE_HISTORY, SECTOR_PERFORMANCE
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


ALL = ["price_history", "sector_performance", "financials"]


def run_graph(monkeypatch, workers, sector_error=None):
    """Run the whole graph with Gemini and the three fetch tools stubbed."""
    monkeypatch.setattr(parse_module, "extract_companies", lambda user_query: ["Nvidia"])
    monkeypatch.setattr(dispatch_module, "choose_workers", lambda user_query, company_name, ticker: workers)
    monkeypatch.setattr(price_history_module, "fetch_price_history", lambda ticker: PRICE_HISTORY)
    monkeypatch.setattr(financials_module, "fetch_financials", lambda ticker: FUNDAMENTALS)

    def fetch_sector(ticker):
        if sector_error:
            raise sector_error
        return SECTOR_PERFORMANCE

    monkeypatch.setattr(sector_performance_module, "fetch_sector_performance", fetch_sector)
    return graph.invoke({"user_query": "Should I buy Nvidia?"})


def test_single_worker_dispatched_gives_one_finding(monkeypatch):
    result = run_graph(monkeypatch, ["financials"])
    assert [f.source for f in result["findings"]] == ["financials"]
    assert result["findings"][0].data == FUNDAMENTALS


def test_all_workers_dispatched_gives_three_distinct_findings(monkeypatch):
    result = run_graph(monkeypatch, ALL)
    assert sorted(f.source for f in result["findings"]) == sorted(ALL)
    assert all(f.error is None for f in result["findings"])


def test_failed_worker_does_not_stop_the_run(monkeypatch):
    result = run_graph(monkeypatch, ALL, sector_error=RuntimeError("no ETF data"))
    by_source = {f.source: f for f in result["findings"]}
    assert len(result["findings"]) == 3
    assert by_source["price_history"].data is not None
    assert by_source["financials"].data is not None
    assert by_source["sector_performance"].data is None
    assert by_source["sector_performance"].error == "no ETF data"


def test_route_after_dispatch_returns_mandates():
    state = AgentState(user_query="q", mandates_dispatched=["price_history", "financials"])
    assert route_after_dispatch(state) == ["price_history", "financials"]
