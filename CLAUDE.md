# Stock Advisor — V1

## What this is
A personal stock advisor. Given a company, it produces an evaluation:
bull case, bear case, and a recommendation with a confidence score.

It also maintains a portfolio. Buys and sells are MOCKED — no real
transactions, ever. The point is to track positions over time and feed
past decisions into future evaluations.

## Who it's for
Individuals analyzing a specific stock and maintaining a paper portfolio.

## Stack — do not substitute without asking
- Orchestration: LangGraph (Python SDK)
- Model: Llama 3.1 via Ollama, http://localhost:11434
- UI: Streamlit
- Python: 3.12+
- Package manager: pip + venv

## Architecture
Research graph:
  parse_query -> load_prior_theses -> supervisor
  supervisor fans out via Send() to N research_worker instances
  research_worker instances fan in to synthesist
  synthesist -> persist_thesis -> END

State uses `Annotated[list[Finding], operator.add]` for the fan-in field.

Portfolio graph (separate): plain functions, not agents.

## Hard rules
1. Workers NEVER state a figure from model weights. Every quantitative
   claim comes from a tool-fetched dict passed into the prompt. A worker's
   job is to interpret data it was given, not to recall it.
2. Portfolio numbers live in SQLite with a real schema. The LLM never
   writes a number we make decisions on.
3. No Streamlit imports anywhere in src/. UI must be swappable.
4. Output is a thesis card with explicit falsifiers, not a bare buy/sell.
5. Prompts live in src/prompts/*.md as files, never inline strings.

## Data model
`theses` — immutable record per evaluation: ticker, date, bull, bear,
recommendation, confidence, falsifiers, sources.
`positions` — ticker, entry price, entry date, size, status,
thesis_id FK -> theses.

A position always points at the thesis that justified it.

## Repo layout
src/graph/     LangGraph nodes, state, edges
src/tools/     data fetchers (yfinance etc.)
src/prompts/   prompt templates
src/store/     SQLite schema + queries
app.py         Streamlit entrypoint
tests/

## Conventions
- Type hints everywhere; pydantic models for graph state and all outputs
- Secrets via .env, never in code
- Tool tests use recorded fixtures, no live network calls

## Commands
uv run streamlit run app.py
uv run pytest
