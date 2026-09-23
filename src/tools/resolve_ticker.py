"""Deterministic company-name -> ticker lookup from a local CSV file."""

import csv
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "tickers.csv"


class TickerResolution(BaseModel):
    is_present: Literal["yes", "no", "ambiguous"]
    ticker: Optional[str] = None


def resolve_ticker(company: str, data_path: Path = DEFAULT_DATA_PATH) -> TickerResolution:
    """Look up `company` in the tickers CSV via case-insensitive substring match."""
    query = company.strip().lower()
    if not query:
        return TickerResolution(is_present="no")

    matched_tickers: set[str] = set()
    with open(data_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if query in row["company"].strip().lower():
                matched_tickers.add(row["ticker"].strip())

    if not matched_tickers:
        return TickerResolution(is_present="no")
    if len(matched_tickers) > 1:
        return TickerResolution(is_present="ambiguous")
    return TickerResolution(is_present="yes", ticker=next(iter(matched_tickers)))
