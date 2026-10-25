## What this is
Given a company name, resolve it to a ticker, research it (price action,
sector performance, financials), and produce a bull/bear thesis.

## Stack — do not substitute without asking
LangGraph (Python SDK) · Gemini (google-genai)
Streamlit · Python 3.12+ · pip + venv

## Architecture
Dynamic fan-out over a fixed set of workers (conditional edge returning a list of node names; no Send()):
  parse_query (extract company -> resolve ticker)
    -> clarifying question / not found / ambiguous -> end
       (surfaced to the UI; disambiguation among candidates is handled in the UI, not the graph)
    -> resolved -> dispatch (Gemini picks a subset of workers from a fixed list based on the query)
    -> parallel: any of {price_history, sector_performance, financials} workers
    -> each worker appends one Finding to state.findings
    -> synthesize -> bull/bear thesis -> end
Workers are deterministic: no LLM calls inside workers.
Planned later: a reviewer loop after the workers, capped by a review_round counter.

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