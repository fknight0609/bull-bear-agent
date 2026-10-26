"""Graph node: fetch fundamentals for the resolved ticker.

Deterministic, no LLM. Appends one Finding; a tool failure becomes a Finding with
`error` set instead of stopping the run."""

import logging

from src.state import AgentState, Finding
from src.tools.fetch_financials import fetch_financials

log = logging.getLogger("advisor.financials")


def financials(state: AgentState) -> dict:
    """Run fetch_financials for `state.ticker` and return it as a single Finding."""
    log.info("Node financials entered: ticker=%r", state.ticker)
    try:
        data = fetch_financials(state.ticker)
    except Exception as exc:
        log.exception("Worker financials failed for ticker=%r", state.ticker)
        return {"findings": [Finding(source="financials", error=str(exc))]}
    log.info("Worker financials result: %s", data)
    return {"findings": [Finding(source="financials", data=data)]}
