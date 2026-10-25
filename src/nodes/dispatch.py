"""Graph node: choose which research workers to run for the resolved company.

Gemini picks a subset of the fixed worker list. If it picks nothing, or the call
fails, every worker runs, since the company is already known."""

import logging
import time
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from src.llm import MODEL, client
from src.state import AgentState, WorkerName

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
ALL_WORKERS: list[WorkerName] = list(get_args(WorkerName))

log = logging.getLogger("advisor.dispatch")


class DispatchPlan(BaseModel):
    workers: list[WorkerName] = []


def choose_workers(user_query: str, company_name: str, ticker: str) -> list[WorkerName]:
    """Ask Gemini which workers the query needs; may be empty."""
    prompt = (PROMPTS_DIR / "dispatch.md").read_text(encoding="utf-8").format(
        user_query=user_query, company_name=company_name, ticker=ticker
    )
    log.info("Gemini call: choose workers (model=%s, prompt=dispatch.md)", MODEL)
    started = time.perf_counter()
    response = client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": DispatchPlan},
    )
    log.info("Gemini response in %.2fs: %s", time.perf_counter() - started, response.text)
    return DispatchPlan.model_validate_json(response.text).workers


def dispatch(state: AgentState) -> dict:
    """Set `mandates_dispatched` to the chosen workers, in fixed order, defaulting to all."""
    log.info("Node dispatch entered: company_name=%r, ticker=%r", state.company_name, state.ticker)
    try:
        chosen = set(choose_workers(state.user_query, state.company_name, state.ticker))
    except Exception:
        log.exception("Worker choice failed, dispatching all workers")
        chosen = set()

    if not chosen:
        log.info("Decision: no workers chosen, dispatching all")
        chosen = set(ALL_WORKERS)

    mandates = [w for w in ALL_WORKERS if w in chosen]
    log.info("Workers dispatched: %s", mandates)
    return {"mandates_dispatched": mandates}
