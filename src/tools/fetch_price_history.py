"""30-day price/volume history and derived signals for a ticker, from yfinance."""

from typing import Literal

import yfinance as yf
from pydantic import BaseModel

LOOKBACK_DAYS = 30


class PriceHistory(BaseModel):
    start_price: float
    end_price: float
    pct_change_30d: float
    high_30d: float
    low_30d: float
    drawdown_from_high: float
    avg_volume_30d: float
    volume_trend: float
    sma_5: float
    sma_20: float
    price_vs_sma20: Literal["above", "below"]
    volatility_30d: float


def fetch_price_history(ticker: str) -> PriceHistory:
    """Fetch the last 30 trading days of daily OHLCV data for `ticker` and derive summary stats."""
    history = yf.Ticker(ticker).history(period="3mo", interval="1d").tail(LOOKBACK_DAYS)
    if len(history) < LOOKBACK_DAYS:
        raise ValueError(f"Not enough trading history for '{ticker}': only {len(history)} days available")

    closes = history["Close"]
    volumes = history["Volume"]

    start_price = float(closes.iloc[0])
    end_price = float(closes.iloc[-1])
    high_30d = float(closes.max())
    sma_20 = float(closes.tail(20).mean())

    daily_returns = closes.pct_change().dropna()
    last_5d_avg_volume = float(volumes.tail(5).mean())
    prior_25d_avg_volume = float(volumes.iloc[:-5].mean())

    return PriceHistory(
        start_price=start_price,
        end_price=end_price,
        pct_change_30d=(end_price - start_price) / start_price,
        high_30d=high_30d,
        low_30d=float(closes.min()),
        drawdown_from_high=(end_price - high_30d) / high_30d,
        avg_volume_30d=float(volumes.mean()),
        volume_trend=last_5d_avg_volume / prior_25d_avg_volume,
        sma_5=float(closes.tail(5).mean()),
        sma_20=sma_20,
        price_vs_sma20="above" if end_price >= sma_20 else "below",
        volatility_30d=float(daily_returns.std()),
    )
