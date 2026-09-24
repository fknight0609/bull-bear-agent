import pandas as pd
import pytest

from src.tools import fetch_financials as module
from src.tools.fetch_financials import fetch_financials

# Recorded fixture: two annual periods, most-recent first (as yfinance returns them).
INCOME = pd.DataFrame(
    {
        "2024": [1_000.0, 400.0, 200.0, 150.0],
        "2023": [800.0, 300.0, 120.0, 80.0],
    },
    index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
)
BALANCE = pd.DataFrame(
    {
        "2024": [500.0, 250.0, 300.0, 100.0, 50.0],
        "2023": [450.0, 220.0, 260.0, 90.0, 45.0],
    },
    index=["Total Debt", "Stockholders Equity", "Current Assets", "Current Liabilities", "Inventory"],
)


class _StubTicker:
    def __init__(self, income: pd.DataFrame, balance: pd.DataFrame):
        self.income_stmt = income
        self.balance_sheet = balance


@pytest.fixture(autouse=True)
def stub_yfinance(monkeypatch):
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(INCOME, BALANCE))


def test_margins():
    result = fetch_financials("AAPL")
    assert result.gross_margin == pytest.approx(400.0 / 1_000.0)
    assert result.operating_margin == pytest.approx(200.0 / 1_000.0)
    assert result.net_margin == pytest.approx(150.0 / 1_000.0)


def test_revenue_growth_yoy():
    result = fetch_financials("AAPL")
    assert result.revenue_growth_yoy == pytest.approx((1_000.0 - 800.0) / 800.0)


def test_debt_ratios():
    result = fetch_financials("AAPL")
    assert result.debt_to_equity == pytest.approx(500.0 / 250.0)
    assert result.current_ratio == pytest.approx(300.0 / 100.0)
    assert result.quick_ratio == pytest.approx((300.0 - 50.0) / 100.0)


def test_raises_when_no_statements(monkeypatch):
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(pd.DataFrame(), pd.DataFrame()))
    with pytest.raises(ValueError, match="No financial statements available"):
        fetch_financials("AAPL")


def test_raises_when_single_period(monkeypatch):
    single_period_income = INCOME[["2024"]]
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(single_period_income, BALANCE))
    with pytest.raises(ValueError, match="Not enough annual periods"):
        fetch_financials("AAPL")


def test_missing_row_raises(monkeypatch):
    broken_income = INCOME.drop(index="Gross Profit")
    monkeypatch.setattr(module.yf, "Ticker", lambda ticker: _StubTicker(broken_income, BALANCE))
    with pytest.raises(ValueError, match="None of"):
        fetch_financials("AAPL")
