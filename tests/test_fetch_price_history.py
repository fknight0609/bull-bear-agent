import pandas as pd
import pytest

from src.tools import fetch_price_history as module
from src.tools.fetch_price_history import fetch_price_history

# Recorded fixture: 30 trading days of closes/volumes, close trending up
# from 100 to a peak of 130 then back down to 120, so drawdown/volume_trend
# both exercise non-trivial branches.
CLOSES = [100 + i for i in range(25)] + [130, 128, 126, 122, 120]
VOLUMES = [1_000_000] * 25 + [3_000_000] * 5


def _fixture_history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.DataFrame({"Close": CLOSES, "Volume": VOLUMES}, index=dates)


class _StubTicker:
    def __init__(self, history: pd.DataFrame):
        self._history = history

    def history(self, period: str, interval: str) -> pd.DataFrame:
        return self._history


@pytest.fixture(autouse=True)
def stub_yfinance(monkeypatch):
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(_fixture_history()))


def test_start_and_end_price():
    result = fetch_price_history("AAPL")
    assert result.start_price == 100
    assert result.end_price == 120


def test_pct_change_30d():
    result = fetch_price_history("AAPL")
    assert result.pct_change_30d == pytest.approx((120 - 100) / 100)


def test_high_low_and_drawdown():
    result = fetch_price_history("AAPL")
    assert result.high_30d == 130
    assert result.low_30d == 100
    assert result.drawdown_from_high == pytest.approx((120 - 130) / 130)


def test_volume_stats():
    result = fetch_price_history("AAPL")
    assert result.avg_volume_30d == pytest.approx(sum(VOLUMES) / len(VOLUMES))
    assert result.volume_trend == pytest.approx(3_000_000 / 1_000_000)


def test_sma_and_price_vs_sma20():
    result = fetch_price_history("AAPL")
    assert result.sma_5 == pytest.approx(sum(CLOSES[-5:]) / 5)
    assert result.sma_20 == pytest.approx(sum(CLOSES[-20:]) / 20)
    assert result.price_vs_sma20 == "above"


def test_raises_when_insufficient_history(monkeypatch):
    short_history = _fixture_history().tail(10)
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(short_history))
    with pytest.raises(ValueError, match="Not enough trading history"):
        fetch_price_history("AAPL")
