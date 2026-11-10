"""Deterministic company-name -> ticker lookup from a local CSV file."""

import csv
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "tickers.csv"


class TickerResolution(BaseModel):
    is_present: Literal["yes", "no", "ambiguous"]
    ticker: Optional[str] = None
    candidates: list[str] = []


def resolve_ticker(company: str, data_path: Path = DEFAULT_DATA_PATH) -> TickerResolution:
    """Look up `company` in the tickers CSV, preferring the closest kind of name match.

    Match tiers, best first: the name starts with the query as a whole word ("Ford" -> "Ford Motor",
    not "Ashford"); the query appears as a whole word anywhere; plain case-insensitive substring.
    Only the best non-empty tier is used."""
    query = company.strip().lower()
    if not query:
        return TickerResolution(is_present="no")

    escaped = re.escape(query)
    tiers = [re.compile(rf"^{escaped}(?!\w)"), re.compile(rf"(?<!\w){escaped}(?!\w)"), re.compile(escaped)]
    matches: list[dict[str, str]] = [{} for _ in tiers]  # per tier: ticker -> company name
    with open(data_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["company"].strip()
            for tier, pattern in zip(matches, tiers):
                if pattern.search(name.lower()):
                    tier[row["ticker"].strip()] = name
                    break  # a name counts only in its best tier

    best = next((tier for tier in matches if tier), {})
    if not best:
        return TickerResolution(is_present="no")
    if len(best) > 1:
        return TickerResolution(is_present="ambiguous", candidates=sorted(set(best.values())))
    return TickerResolution(is_present="yes", ticker=next(iter(best)))
