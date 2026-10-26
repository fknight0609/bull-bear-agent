import pytest

from src.nodes import financials as financials_module
from src.nodes import price_history as price_history_module
from src.nodes import sector_performance as sector_performance_module
from src.state import AgentState
from src.tools.fetch_financials import Fundamentals
from src.tools.fetch_price_history import PriceHistory
from src.tools.fetch_sector_performance import SectorPerformance
from src.tools.resolve_ticker import TickerResolution

PRICE_HISTORY = PriceHistory(
    start_price=100.0, end_price=110.0, pct_change_30d=10.0, high_30d=112.0, low_30d=98.0,
    drawdown_from_high=1.8, avg_volume_30d=1e6, volume_trend=0.1, sma_5=108.0, sma_20=105.0,
    price_vs_sma20="above", volatility_30d=0.3,
)
SECTOR_PERFORMANCE = SectorPerformance(
    sector="Technology", etf_proxy="XLK", pct_change_30d=4.0, high_30d=210.0, low_30d=195.0,
    sma_20=200.0, price_vs_sma20="above", volatility_30d=0.2,
)
FUNDAMENTALS = Fundamentals(
    gross_margin=0.7, operating_margin=0.5, net_margin=0.4, revenue_growth_yoy=0.3,
    debt_to_equity=0.4, current_ratio=4.0, quick_ratio=3.5,
)

# (worker name, module, tool name, tool result)
WORKERS = [
    ("price_history", price_history_module, "fetch_price_history", PRICE_HISTORY),
    ("sector_performance", sector_performance_module, "fetch_sector_performance", SECTOR_PERFORMANCE),
    ("financials", financials_module, "fetch_financials", FUNDAMENTALS),
]


@pytest.fixture
def state() -> AgentState:
    return AgentState(
        user_query="Is Nvidia a buy?",
        company_name="Nvidia",
        resolution=TickerResolution(is_present="yes", ticker="NVDA"),
    )


@pytest.mark.parametrize("name, module, tool, result", WORKERS)
def test_worker_returns_tool_data(monkeypatch, state, name, module, tool, result):
    calls = []
    monkeypatch.setattr(module, tool, lambda ticker: calls.append(ticker) or result)
    (finding,) = getattr(module, name)(state)["findings"]
    assert calls == ["NVDA"]
    assert finding.source == name
    assert finding.data is result
    assert finding.error is None


@pytest.mark.parametrize("name, module, tool, result", WORKERS)
def test_worker_failure_becomes_error_finding(monkeypatch, state, name, module, tool, result):
    def boom(ticker):
        raise RuntimeError("yfinance down")

    monkeypatch.setattr(module, tool, boom)
    (finding,) = getattr(module, name)(state)["findings"]
    assert finding.source == name
    assert finding.data is None
    assert finding.error == "yfinance down"
