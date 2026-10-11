## What this is
Given a company name, resolve it to a ticker, research it (price action,
sector performance, financials), and produce a bull/bear thesis.

## Stack — do not substitute without asking
LangGraph (Python SDK) · Gemini (google-genai)
Streamlit · Python 3.12+ · pip + venv

## Architecture
Static fan-out (fixed node set, no Send()):
  start (resolve_ticker: company name -> ticker)
    -> not found / ambiguous -> end (surfaced as an error to the UI;
       disambiguation among multiple matches is handled in the UI, not the graph)
    -> resolved -> fan-out parallel: {fetch_price_history, fetch_sector_performance, fetch_financials}
    -> synthesize -> bull/bear thesis -> end

## Hard rules
1. The model NEVER states a figure from its own weights. Every
   quantitative claim comes from a tool-fetched dict passed into the
   prompt. The model interprets data it was given; it does not recall it.
2. All arithmetic happens in Python, not in the prompt.
3. No Streamlit imports anywhere in src/. UI must be swappable.
4. Prompts live in src/prompts/*.md as files, never inline strings.

## Repo layout
src/tools/     data fetchers (yfinance)
src/nodes/     one graph node per file
src/graph.py   wires nodes into the LangGraph graph
src/prompts/   prompt templates
app.py         Streamlit entrypoint
tests/
src/tests/     unrelated test functions

## Conventions
Type hints everywhere; pydantic models for all tool returns.
Secrets via .env. Tool tests use recorded fixtures, no live network calls.

## Commands
streamlit run app.py
pytest