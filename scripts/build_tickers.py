"""Rebuild src/tools/data/tickers.csv from public listings.

US: NASDAQ Trader symbol directory (NASDAQ, NYSE, NYSE American and other US venues).
UK: FTSE 100, FTSE 250 and FTSE SmallCap constituent tables on Wikipedia (not every LSE listing).

Tickers are written in Yahoo Finance form (BRK-B, HSBA.L) because the fetch tools use yfinance.
Run: python scripts/build_tickers.py
"""

import csv
import re
import ssl
import urllib.request
from io import StringIO
from pathlib import Path

import certifi
import pandas as pd

OUT_PATH = Path(__file__).parent.parent / "src" / "tools" / "data" / "tickers.csv"
USER_AGENT = "Mozilla/5.0 (compatible; FinancialAdvisorDataFetch/1.0)"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
FTSE_PAGES = ["FTSE_100_Index", "FTSE_250_Index", "FTSE_SmallCap_Index"]

OTHER_EXCHANGES = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Z": "Cboe BZX", "V": "IEX"}

# Securities that are not the company's common equity: warrants, rights, preferreds, debt, units.
NOT_COMMON_NAME = re.compile(
    r"\bwarrants?\b|\brights?\b|\bpreferred\b|\bpreference\b|\bnotes?\b|\bdebentures?\b|\bsubordinated\b|\d%",
    re.IGNORECASE,
)
NOT_COMMON_SYMBOL = re.compile(r"[$^]|\.(WS|WSA|WSB|RT|U)$")
# Boilerplate after the company name, e.g. "Inc. Common Stock", "Class A Ordinary Shares".
SECURITY_SUFFIX = re.compile(
    r"(?:\s+|(?<=[.)]))(?:(Class\s+[A-Z0-9]+)\s+)?(?:New\s+)?"
    r"(?:Common Stock|Common Shares|Ordinary Shares?|Capital Stock|Depositary Shares|"
    r"American Depositary (?:Shares|Receipts?)|Shares of Beneficial Interest|Common Units?|Units?)\b.*$",
    re.IGNORECASE,
)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=60, context=context) as response:
        return response.read().decode("utf-8")


def is_common_equity(name: str, symbol: str) -> bool:
    if NOT_COMMON_NAME.search(name) or NOT_COMMON_SYMBOL.search(symbol):
        return False
    # "Units" are SPAC bundles and similar, but master limited partnership "Common Units" are real equity.
    return not (re.search(r"\bunits?\b", name, re.IGNORECASE) and "common unit" not in name.lower())


def clean_name(raw: str) -> str:
    """Strip security-type boilerplate but keep the share class, so classes stay distinguishable."""
    name, _, descriptor = raw.partition(" - ")
    name = name.strip()
    class_match = re.match(r"(Class\s+[A-Z0-9]+)\b", descriptor.strip(), re.IGNORECASE)
    if descriptor:
        return f"{name} {class_match.group(1)}" if class_match else name
    suffix = SECURITY_SUFFIX.search(name)
    if suffix:
        return f"{name[: suffix.start()]} {suffix.group(1)}".strip() if suffix.group(1) else name[: suffix.start()]
    return name


def yahoo_us_symbol(symbol: str) -> str:
    return symbol.strip().replace(".", "-")


def parse_pipe_file(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("File Creation Time")]
    return list(csv.DictReader(lines, delimiter="|"))


def us_rows() -> list[tuple[str, str, str]]:
    rows = []
    for row in parse_pipe_file(fetch(NASDAQ_LISTED_URL)):
        if row["Test Issue"] == "Y" or row["ETF"] == "Y" or row["NextShares"] == "Y":
            continue
        if is_common_equity(row["Security Name"], row["Symbol"]):
            rows.append((clean_name(row["Security Name"]), yahoo_us_symbol(row["Symbol"]), "NASDAQ"))
    for row in parse_pipe_file(fetch(OTHER_LISTED_URL)):
        if row["Test Issue"] == "Y" or row["ETF"] == "Y":
            continue
        if is_common_equity(row["Security Name"], row["ACT Symbol"]):
            exchange = OTHER_EXCHANGES.get(row["Exchange"], "US")
            rows.append((clean_name(row["Security Name"]), yahoo_us_symbol(row["ACT Symbol"]), exchange))
    return rows


def yahoo_uk_symbol(epic: str) -> str:
    epic = re.sub(r"\[.*?\]", "", epic).strip().rstrip(".")
    return re.sub(r"[^A-Z0-9-]", "", epic.upper().replace(".", "-")) + ".L"


def uk_rows() -> list[tuple[str, str, str]]:
    rows = []
    for page in FTSE_PAGES:
        html = fetch(f"https://en.wikipedia.org/wiki/{page}")
        for table in pd.read_html(StringIO(html)):
            if {"Company", "Ticker"} <= set(map(str, table.columns)):
                for company, ticker in zip(table["Company"], table["Ticker"]):
                    rows.append((re.sub(r"\[.*?\]", "", str(company)).strip(), yahoo_uk_symbol(str(ticker)), "LSE"))
    return rows


def main() -> None:
    seen: set[str] = set()
    unique = []
    for company, ticker, exchange in us_rows() + uk_rows():
        if ticker not in seen and company and ticker != ".L":
            seen.add(ticker)
            unique.append((company, ticker, exchange))
    # Two listings with the same name (share classes, US and UK lines) get the ticker appended so candidates differ.
    name_counts = {name: sum(1 for row in unique if row[0] == name) for name in {row[0] for row in unique}}
    unique = [(f"{c} ({t})" if name_counts[c] > 1 else c, t, e) for c, t, e in unique]
    unique.sort(key=lambda row: (row[0].lower(), row[1]))

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company", "ticker", "exchange"])
        writer.writerows(unique)
    print(f"Wrote {len(unique)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
