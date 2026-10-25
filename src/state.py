"""Graph state schema shared by all nodes."""

import operator
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, model_validator

from src.tools.fetch_financials import Fundamentals
from src.tools.fetch_price_history import PriceHistory
from src.tools.fetch_sector_performance import SectorPerformance
from src.tools.resolve_ticker import TickerResolution

WorkerName = Literal["price_history", "sector_performance", "financials"]


class Finding(BaseModel):
    """One worker's result: either its tool data or an error, never both."""

    source: WorkerName
    data: Optional[PriceHistory | SectorPerformance | Fundamentals] = None
    error: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_of_data_or_error(self) -> "Finding":
        if (self.data is None) == (self.error is None):
            raise ValueError("Finding requires exactly one of data or error")
        return self


class AgentState(BaseModel):
    user_query: str
    company_name: Optional[str] = None
    resolution: Optional[TickerResolution] = None
    clarifying_question: Optional[str] = None
    mandates_dispatched: list[WorkerName] = []  # written only by dispatch
    findings: Annotated[list[Finding], operator.add] = []  # fan-in: each worker appends one

    @property
    def ticker(self) -> Optional[str]:
        return self.resolution.ticker if self.resolution else None
