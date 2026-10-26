"""Graph node: fetch 30-day price history for the resolved ticker.

Deterministic, no LLM. Appends one Finding; a tool failure becomes a Finding with
`error` set instead of stopping the run."""

import logging

from src.state import AgentState, Finding
from src.tools.fetch_price_history import fetch_price_history

log = logging.getLogger("advisor.price_history")


def price_history(state: AgentState) -> dict:
    """Run fetch_price_history for `state.ticker` and return it as a single Finding."""
    log.info("Node price_history entered: ticker=%r", state.ticker)
    try:
        data = fetch_price_history(state.ticker)
    except Exception as exc:
        log.exception("Worker price_history failed for ticker=%r", state.ticker)
        return {"findings": [Finding(source="price_history", error=str(exc))]}
    log.info("Worker price_history result: %s", data)
    return {"findings": [Finding(source="price_history", data=data)]}
