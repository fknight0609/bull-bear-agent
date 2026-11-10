"""Graph node: turn the workers' findings into a bull/bear thesis.

Python builds the data dict (formatting and arithmetic); Gemini only interprets it.
With no successful finding, or if Gemini fails, a fixed fallback thesis is returned."""

import json
import logging
import time
from pathlib import Path
from typing import get_args

from src.llm import MODEL, client
from src.state import AgentState, Finding, Thesis, WorkerName

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
ALL_WORKERS: list[WorkerName] = list(get_args(WorkerName))

# Fraction fields shown as percentage strings; every other number is rounded to 2 places.
PERCENT_FIELDS = {
    "pct_change_30d",
    "drawdown_from_high",
    "volatility_30d",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "revenue_growth_yoy",
}

log = logging.getLogger("advisor.synthesize")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_section(data: dict) -> dict:
    return {
        key: _percent(value) if key in PERCENT_FIELDS else round(value, 2) if isinstance(value, float) else value
        for key, value in data.items()
    }


def build_data(findings: list[Finding], mandates_dispatched: list[WorkerName]) -> dict:
    """Pure-Python data dict for the prompt: one section per successful finding, plus derived and missing."""
    raw = {f.source: f.data.model_dump() for f in findings if f.data is not None}
    data: dict = {source: _format_section(values) for source, values in raw.items()}

    if "price_history" in raw and "sector_performance" in raw:
        relative = raw["price_history"]["pct_change_30d"] - raw["sector_performance"]["pct_change_30d"]
        data["derived"] = {"relative_return_30d": _percent(relative)}

    data["missing"] = [f"{f.source}: {f.error}" for f in findings if f.error is not None] + [
        f"{w}: not dispatched" for w in ALL_WORKERS if w not in mandates_dispatched
    ]
    return data


def evidence_keys(data: dict) -> set[str]:
    """Every "section.field" key a thesis point may cite."""
    return {f"{section}.{field}" for section, values in data.items() if section != "missing" for field in values}


def write_thesis(user_query: str, company_name: str, ticker: str, data: dict) -> Thesis:
    """Ask Gemini to interpret `data` as a bull/bear thesis."""
    prompt = (PROMPTS_DIR / "synthesize.md").read_text(encoding="utf-8").format(
        user_query=user_query,
        company_name=company_name,
        ticker=ticker,
        data=json.dumps(data, indent=2),
    )
    log.info("Gemini call: write thesis (model=%s, prompt=synthesize.md)", MODEL)
    started = time.perf_counter()
    response = client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": Thesis},
    )
    log.info("Gemini response in %.2fs: %s", time.perf_counter() - started, response.text)
    return Thesis.model_validate_json(response.text)


def drop_invalid_evidence(thesis: Thesis, valid: set[str]) -> Thesis:
    """Remove evidence keys that are not in the data dict, warning for each one."""
    for point in thesis.bull_points + thesis.bear_points:
        for key in point.evidence:
            if key not in valid:
                log.warning("Dropped unknown evidence key %r from claim %r", key, point.claim)
        point.evidence = [key for key in point.evidence if key in valid]
    return thesis


def synthesize(state: AgentState) -> dict:
    """Write `thesis` from the findings gathered by the workers."""
    log.info("Node synthesize entered: %d findings", len(state.findings))
    data = build_data(state.findings, state.mandates_dispatched)
    log.info("Data built: %s", data)

    if not any(f.data is not None for f in state.findings):
        log.info("Decision: no successful findings, returning fixed thesis without calling Gemini")
        thesis = Thesis(
            summary="No data was available to answer this question.",
            bull_points=[],
            bear_points=[],
            missing=data["missing"],
        )
        return {"thesis": thesis}

    try:
        thesis = write_thesis(state.user_query, state.company_name, state.ticker, data)
    except Exception:
        log.exception("Thesis generation failed, returning fallback thesis")
        return {
            "thesis": Thesis(
                summary="Synthesis failed, so no thesis could be written.",
                bull_points=[],
                bear_points=[],
                missing=data["missing"],
            )
        }

    thesis = drop_invalid_evidence(thesis, evidence_keys(data))
    log.info("Thesis written: %d bull, %d bear points", len(thesis.bull_points), len(thesis.bear_points))
    return {"thesis": thesis}
