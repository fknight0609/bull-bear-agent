"""Fundamentals (margins, revenue growth, debt ratios) for a ticker, from yfinance.

Computes derived ratios from the raw income statement / balance sheet; the
model never sees the statements themselves, only the resulting dict.
"""

import pandas as pd
import yfinance as yf
from pydantic import BaseModel


class Fundamentals(BaseModel):
    gross_margin: float
    operating_margin: float
    net_margin: float
    revenue_growth_yoy: float
    debt_to_equity: float
    current_ratio: float
    quick_ratio: float


def _row(statement: pd.DataFrame, *labels: str) -> pd.Series:
    """Return the first row in `statement` matching one of `labels`."""
    for label in labels:
        if label in statement.index:
            return statement.loc[label]
    raise ValueError(f"None of {labels} found in statement rows: {list(statement.index)}")


def _optional_row(statement: pd.DataFrame, *labels: str) -> pd.Series:
    """Like `_row`, but returns an all-zero series instead of raising if no label matches."""
    for label in labels:
        if label in statement.index:
            return statement.loc[label]
    return pd.Series(0.0, index=statement.columns)


def fetch_financials(ticker: str) -> Fundamentals:
    """Fetch annual income statement + balance sheet for `ticker` and derive fundamentals."""
    company = yf.Ticker(ticker)
    income = company.income_stmt
    balance = company.balance_sheet

    if income is None or income.empty or balance is None or balance.empty:
        raise ValueError(f"No financial statements available for '{ticker}'")

    revenue = _row(income, "Total Revenue")
    if len(revenue) < 2:
        raise ValueError(f"Not enough annual periods for '{ticker}' to compute revenue growth")

    gross_profit = _row(income, "Gross Profit")
    operating_income = _row(income, "Operating Income")
    net_income = _row(income, "Net Income", "Net Income Common Stockholders")

    latest_revenue = float(revenue.iloc[0])
    prior_revenue = float(revenue.iloc[1])

    total_debt = _row(balance, "Total Debt")
    equity = _row(balance, "Stockholders Equity", "Total Stockholder Equity")
    current_assets = _row(balance, "Current Assets", "Total Current Assets")
    current_liabilities = _row(balance, "Current Liabilities", "Total Current Liabilities")
    inventory = _optional_row(balance, "Inventory")

    current_liabilities_latest = float(current_liabilities.iloc[0])

    return Fundamentals(
        gross_margin=float(gross_profit.iloc[0]) / latest_revenue,
        operating_margin=float(operating_income.iloc[0]) / latest_revenue,
        net_margin=float(net_income.iloc[0]) / latest_revenue,
        revenue_growth_yoy=(latest_revenue - prior_revenue) / prior_revenue,
        debt_to_equity=float(total_debt.iloc[0]) / float(equity.iloc[0]),
        current_ratio=float(current_assets.iloc[0]) / current_liabilities_latest,
        quick_ratio=(float(current_assets.iloc[0]) - float(inventory.iloc[0])) / current_liabilities_latest,
    )
