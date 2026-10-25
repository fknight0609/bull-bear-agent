import pytest

from src.nodes import dispatch as module
from src.nodes.dispatch import dispatch
from src.state import AgentState
from src.tools.resolve_ticker import TickerResolution

ALL = ["price_history", "sector_performance", "financials"]


@pytest.fixture
def state() -> AgentState:
    return AgentState(
        user_query="What are Nvidia's margins?",
        company_name="Nvidia",
        resolution=TickerResolution(is_present="yes", ticker="NVDA"),
    )


def stub(monkeypatch, workers):
    monkeypatch.setattr(module, "choose_workers", lambda user_query, company_name, ticker: workers)


def test_narrow_pick_is_passed_through(monkeypatch, state):
    stub(monkeypatch, ["financials"])
    assert dispatch(state) == {"mandates_dispatched": ["financials"]}


def test_duplicates_and_order_are_normalised(monkeypatch, state):
    stub(monkeypatch, ["financials", "price_history", "financials"])
    assert dispatch(state) == {"mandates_dispatched": ["price_history", "financials"]}


def test_empty_pick_dispatches_all(monkeypatch, state):
    stub(monkeypatch, [])
    assert dispatch(state) == {"mandates_dispatched": ALL}


def test_gemini_failure_dispatches_all(monkeypatch, state):
    def boom(user_query, company_name, ticker):
        raise RuntimeError("Gemini down")

    monkeypatch.setattr(module, "choose_workers", boom)
    assert dispatch(state) == {"mandates_dispatched": ALL}
