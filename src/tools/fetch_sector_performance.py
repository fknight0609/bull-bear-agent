"""Sector performance for a ticker, proxied by its SPDR sector ETF, from yfinance."""

from typing import Literal

import yfinance as yf
from pydantic import BaseModel

LOOKBACK_DAYS = 30

# yfinance's `sector` field uses GICS sector names; map each to its SPDR sector ETF.
SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


class SectorPerformance(BaseModel):
    sector: str
    etf_proxy: str
    pct_change_30d: float
    high_30d: float
    low_30d: float
    sma_20: float
    price_vs_sma20: Literal["above", "below"]
    volatility_30d: float


def fetch_sector_performance(ticker: str) -> SectorPerformance:
    """Resolve `ticker`'s sector to its SPDR sector ETF, then derive 30-day performance stats for that ETF."""
    sector = yf.Ticker(ticker).info.get("sector")
    if not sector:
        raise ValueError(f"No sector found for '{ticker}'")

    etf_proxy = SECTOR_ETF_MAP.get(sector)
    if etf_proxy is None:
        raise ValueError(f"No ETF proxy mapped for sector '{sector}'")

    history = yf.Ticker(etf_proxy).history(period="3mo", interval="1d").tail(LOOKBACK_DAYS)
    if len(history) < LOOKBACK_DAYS:
        raise ValueError(
            f"Not enough trading history for sector ETF '{etf_proxy}': only {len(history)} days available"
        )

    closes = history["Close"]
    start_price = float(closes.iloc[0])
    end_price = float(closes.iloc[-1])
    sma_20 = float(closes.tail(20).mean())
    daily_returns = closes.pct_change().dropna()

    return SectorPerformance(
        sector=sector,
        etf_proxy=etf_proxy,
        pct_change_30d=(end_price - start_price) / start_price,
        high_30d=float(closes.max()),
        low_30d=float(closes.min()),
        sma_20=sma_20,
        price_vs_sma20="above" if end_price >= sma_20 else "below",
        volatility_30d=float(daily_returns.std()),
    )
