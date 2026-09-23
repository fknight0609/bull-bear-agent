## What this is
Given a ticker, produce an evaluation of the stock: an interpretation of
recent price and sector performance, and a recommendation.

## Stack — do not substitute without asking
LangGraph (Python SDK) · Llama 3.1 via Ollama (http://localhost:11434)
Streamlit · Python 3.12+ · pip + venv

## Architecture
Static fan-out with branching (fixed node set, no Send()):
  start -> {fetch_price_history, fetch_sector_performance}  (parallel)
  both -> research
  research -> conditional edge -> recommend | insufficient_data -> back to research

## Hard rules
1. The model NEVER states a figure from its own weights. Every
   quantitative claim comes from a tool-fetched dict passed into the
   prompt. The model interprets data it was given; it does not recall it.
2. All arithmetic happens in Python, not in the prompt.
3. No Streamlit imports anywhere in src/. UI must be swappable.
4. Prompts live in src/prompts/*.md as files, never inline strings.

## Repo layout
src/tools/     data fetchers (yfinance)
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