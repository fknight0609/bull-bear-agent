"""Graph node: identify the company in the user's query and look up its ticker.

If the node cannot tell which single company the user means, it asks a clarifying
question instead. Ticker lookup outcomes (yes / no / ambiguous) are passed through as-is."""

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

from src.state import AgentState
from src.tools.resolve_ticker import TickerResolution, resolve_ticker

MODEL = "gemini-3.8-flash"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

log = logging.getLogger("advisor.parse_query")

load_dotenv()


class ParsedQuery(BaseModel):
    companies: list[str] = []


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def extract_companies(user_query: str) -> list[str]:
    """Ask Gemini which companies the user mentions; empty if none."""
    prompt = (PROMPTS_DIR / "parse_query.md").read_text(encoding="utf-8").format(user_query=user_query)
    log.info("Gemini call: extract companies (model=%s, prompt=parse_query.md)", MODEL)
    response = _client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": ParsedQuery},
    )
    log.info("Gemini response: %s", response.text)
    companies = ParsedQuery.model_validate_json(response.text).companies
    return [c.strip() for c in companies if c.strip()]


def ask_clarifying_question(user_query: str, reason: str, options: list[str]) -> str:
    """Ask Gemini to phrase a clarifying question, offering `options` when there are any."""
    prompt = (PROMPTS_DIR / "clarify_query.md").read_text(encoding="utf-8").format(
        user_query=user_query,
        reason=reason,
        options="\n".join(f"- {o}" for o in options) or "(none)",
    )
    log.info("Gemini call: clarifying question (model=%s, reason=%r, options=%s)", MODEL, reason, options)
    response = _client().models.generate_content(model=MODEL, contents=prompt)
    log.info("Gemini response: %s", response.text.strip())
    return response.text.strip()


def parse_query(state: AgentState) -> dict:
    """Identify the company in `state.user_query` and resolve it, or set `clarifying_question`."""
    user_query = state.user_query
    log.info("Node parse_query entered: user_query=%r", user_query)
    companies = extract_companies(user_query)
    log.info("Companies extracted: %s", companies)

    if not companies:
        log.info("Decision: no company found, asking which one")
        question = ask_clarifying_question(user_query, "No company was identified in the message.", [])
        return {"company_name": None, "resolution": TickerResolution(is_present="no"), "clarifying_question": question}

    if len(companies) > 1:
        log.info("Decision: several companies found, asking user to pick one")
        question = ask_clarifying_question(
            user_query, "The message mentions several companies; only one can be researched at a time.", companies
        )
        return {"company_name": None, "resolution": TickerResolution(is_present="no"), "clarifying_question": question}

    company_name = companies[0]
    resolution = resolve_ticker(company_name)
    log.info("Ticker lookup for %r: %s", company_name, resolution.model_dump())
    return {"company_name": company_name, "resolution": resolution, "clarifying_question": None}
