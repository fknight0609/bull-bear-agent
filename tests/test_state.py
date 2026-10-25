import operator

import pytest
from pydantic import ValidationError

from src.state import AgentState, Finding
from src.tools.fetch_financials import Fundamentals
from src.tools.resolve_ticker import TickerResolution


def _fundamentals() -> Fundamentals:
    return Fundamentals(
        gross_margin=0.4,
        operating_margin=0.3,
        net_margin=0.2,
        revenue_growth_yoy=0.1,
        debt_to_equity=1.0,
        current_ratio=1.5,
        quick_ratio=1.2,
    )


def test_finding_with_data_only_is_valid():
    finding = Finding(source="financials", data=_fundamentals())
    assert finding.error is None


def test_finding_with_error_only_is_valid():
    finding = Finding(source="financials", error="boom")
    assert finding.data is None


def test_finding_with_both_data_and_error_raises():
    with pytest.raises(ValidationError):
        Finding(source="financials", data=_fundamentals(), error="boom")


def test_finding_with_neither_data_nor_error_raises():
    with pytest.raises(ValidationError):
        Finding(source="financials")


def test_ticker_is_none_without_resolution():
    assert AgentState(user_query="q").ticker is None


def test_ticker_comes_from_resolution():
    state = AgentState(user_query="q", resolution=TickerResolution(is_present="yes", ticker="TSLA"))
    assert state.ticker == "TSLA"


def test_findings_reducer_concatenates():
    a = [Finding(source="financials", error="a")]
    b = [Finding(source="price_history", error="b")]
    assert operator.add(a, b) == a + b
