import pandas as pd
import pytest

from src.tools import fetch_sector_performance as module
from src.tools.fetch_sector_performance import fetch_sector_performance

# Recorded fixture: 30 trading days of ETF closes, trending up from 100 to 120.
CLOSES = [100 + i for i in range(25)] + [130, 128, 126, 122, 120]


def _fixture_history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.DataFrame({"Close": CLOSES}, index=dates)


class _StubTicker:
    def __init__(self, info: dict | None = None, history: pd.DataFrame | None = None):
        self.info = info or {}
        self._history = history

    def history(self, period: str, interval: str) -> pd.DataFrame:
        return self._history


@pytest.fixture(autouse=True)
def stub_yfinance(monkeypatch):
    def fake_ticker(ticker: str):
        if ticker == "AAPL":
            return _StubTicker(info={"sector": "Technology"})
        if ticker == "XLK":
            return _StubTicker(history=_fixture_history())
        raise AssertionError(f"Unexpected ticker requested: {ticker}")

    monkeypatch.setattr(module.yf, "Ticker", fake_ticker)


def test_resolves_sector_and_etf_proxy():
    result = fetch_sector_performance("AAPL")
    assert result.sector == "Technology"
    assert result.etf_proxy == "XLK"


def test_pct_change_30d():
    result = fetch_sector_performance("AAPL")
    assert result.pct_change_30d == pytest.approx((120 - 100) / 100)


def test_high_low():
    result = fetch_sector_performance("AAPL")
    assert result.high_30d == 130
    assert result.low_30d == 100


def test_sma_and_price_vs_sma20():
    result = fetch_sector_performance("AAPL")
    assert result.sma_20 == pytest.approx(sum(CLOSES[-20:]) / 20)
    assert result.price_vs_sma20 == "above"


def test_raises_when_sector_missing(monkeypatch):
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(info={}))
    with pytest.raises(ValueError, match="No sector found"):
        fetch_sector_performance("AAPL")


def test_raises_when_sector_unmapped(monkeypatch):
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(info={"sector": "Made Up Sector"}))
    with pytest.raises(ValueError, match="No ETF proxy mapped"):
        fetch_sector_performance("AAPL")


def test_raises_when_insufficient_history(monkeypatch):
    def fake_ticker(ticker: str):
        if ticker == "AAPL":
            return _StubTicker(info={"sector": "Technology"})
        return _StubTicker(history=_fixture_history().tail(10))

    monkeypatch.setattr(module.yf, "Ticker", fake_ticker)
    with pytest.raises(ValueError, match="Not enough trading history"):
        fetch_sector_performance("AAPL")
