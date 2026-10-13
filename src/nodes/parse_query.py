"""Graph node: identify the company in the user's query and look up its ticker.

If the node cannot tell which single company the user means, it asks a clarifying
question instead. Ticker lookup outcomes (yes / no / ambiguous) are passed through as-is."""

import os
from pathlib import Path
from typing import Optional, TypedDict

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

from src.tools.resolve_ticker import TickerResolution, resolve_ticker

MODEL = "gemini-3.8-flash"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

load_dotenv()


class ParsedQuery(BaseModel):
    companies: list[str] = []


class ParseQueryState(TypedDict, total=False):
    user_query: str
    company_name: Optional[str]
    resolution: TickerResolution
    clarifying_question: Optional[str]


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def extract_companies(user_query: str) -> list[str]:
    """Ask Gemini which companies the user mentions; empty if none."""
    prompt = (PROMPTS_DIR / "parse_query.md").read_text(encoding="utf-8").format(user_query=user_query)
    response = _client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": ParsedQuery},
    )
    companies = ParsedQuery.model_validate_json(response.text).companies
    return [c.strip() for c in companies if c.strip()]


def ask_clarifying_question(user_query: str, reason: str, options: list[str]) -> str:
    """Ask Gemini to phrase a clarifying question, offering `options` when there are any."""
    prompt = (PROMPTS_DIR / "clarify_query.md").read_text(encoding="utf-8").format(
        user_query=user_query,
        reason=reason,
        options="\n".join(f"- {o}" for o in options) or "(none)",
    )
    response = _client().models.generate_content(model=MODEL, contents=prompt)
    return response.text.strip()


def parse_query(state: ParseQueryState) -> ParseQueryState:
    """Identify the company in `state["user_query"]` and resolve it, or set `clarifying_question`."""
    user_query = state["user_query"]
    companies = extract_companies(user_query)

    if not companies:
        question = ask_clarifying_question(user_query, "No company was identified in the message.", [])
        return {"company_name": None, "resolution": TickerResolution(is_present="no"), "clarifying_question": question}

    if len(companies) > 1:
        question = ask_clarifying_question(
            user_query, "The message mentions several companies; only one can be researched at a time.", companies
        )
        return {"company_name": None, "resolution": TickerResolution(is_present="no"), "clarifying_question": question}

    company_name = companies[0]
    return {"company_name": company_name, "resolution": resolve_ticker(company_name), "clarifying_question": None}
