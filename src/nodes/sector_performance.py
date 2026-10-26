"""Graph node: fetch sector ETF performance for the resolved ticker.

Deterministic, no LLM. Appends one Finding; a tool failure becomes a Finding with
`error` set instead of stopping the run."""

import logging

from src.state import AgentState, Finding
from src.tools.fetch_sector_performance import fetch_sector_performance

log = logging.getLogger("advisor.sector_performance")


def sector_performance(state: AgentState) -> dict:
    """Run fetch_sector_performance for `state.ticker` and return it as a single Finding."""
    log.info("Node sector_performance entered: ticker=%r", state.ticker)
    try:
        data = fetch_sector_performance(state.ticker)
    except Exception as exc:
        log.exception("Worker sector_performance failed for ticker=%r", state.ticker)
        return {"findings": [Finding(source="sector_performance", error=str(exc))]}
    log.info("Worker sector_performance result: %s", data)
    return {"findings": [Finding(source="sector_performance", data=data)]}
