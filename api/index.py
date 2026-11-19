"""HTTP adapter for the research graph. No business logic: it only calls graph.invoke."""

import logging
import os
import secrets
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

from src.graph import graph
from src.state import AgentState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("advisor")

app = FastAPI(title="Financial Advisor API")

allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Depends(api_key_header)) -> None:
    """Reject requests without the shared key. Fails closed if API_KEY isn't configured."""
    expected = os.environ.get("API_KEY")
    if not expected:
        log.error("API_KEY is not set; rejecting request")
        raise HTTPException(status_code=503, detail="Service not configured")
    if not provided or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class ResearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/research", dependencies=[Depends(require_api_key)])
def research(request: ResearchRequest) -> Any:
    started = time.perf_counter()
    try:
        log.info("Graph invoked: user_query=%r", request.query)
        result = graph.invoke({"user_query": request.query})
        log.info("Graph invoke took %.2fs", time.perf_counter() - started)
        state = AgentState.model_validate(result)
        log.info(
            "Graph finished: ticker=%s dispatched=%s findings=%s thesis=%s",
            state.ticker,
            state.mandates_dispatched,
            [(f.source, "error" if f.error else "ok") for f in state.findings],
            "yes" if state.thesis else "no",
        )
        return state.model_dump(mode="json")
    except Exception as e:
        # Server-side only: the client just gets "Research failed".
        log.exception("Graph failed after %.2fs: %s: %s", time.perf_counter() - started, type(e).__name__, e)
        content = {"detail": "Research failed"}
        if os.environ.get("EXPOSE_ERRORS") == "1":  # local debugging only; never set this on a deployment
            content["error"] = f"{type(e).__name__}: {e}"
        return JSONResponse(status_code=500, content=content)
