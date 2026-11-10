import pytest

from src.nodes import synthesize as module
from src.nodes.synthesize import build_data, synthesize
from src.state import AgentState, Finding, Thesis, ThesisPoint
from src.tools.resolve_ticker import TickerResolution
from tests.test_workers import FUNDAMENTALS, PRICE_HISTORY, SECTOR_PERFORMANCE

ALL = ["price_history", "sector_performance", "financials"]

PRICE_FINDING = Finding(source="price_history", data=PRICE_HISTORY)
SECTOR_FINDING = Finding(source="sector_performance", data=SECTOR_PERFORMANCE)
FINANCIALS_FINDING = Finding(source="financials", data=FUNDAMENTALS)


def make_state(findings, mandates=ALL) -> AgentState:
    return AgentState(
        user_query="Should I buy Nvidia?",
        company_name="Nvidia",
        resolution=TickerResolution(is_present="yes", ticker="NVDA"),
        mandates_dispatched=mandates,
        findings=findings,
    )


def test_build_data_formats_fractions_as_percent_and_rounds_the_rest():
    data = build_data([PRICE_FINDING, FINANCIALS_FINDING], ["price_history", "financials"])
    assert data["price_history"]["pct_change_30d"] == "10.0%"
    assert data["price_history"]["drawdown_from_high"] == "-1.8%"
    assert data["price_history"]["volatility_30d"] == "3.0%"
    assert data["price_history"]["end_price"] == 110.0
    assert data["price_history"]["price_vs_sma20"] == "above"
    assert data["financials"]["gross_margin"] == "70.0%"
    assert data["financials"]["revenue_growth_yoy"] == "30.0%"
    assert data["financials"]["debt_to_equity"] == 0.4


def test_build_data_derives_relative_return_only_when_both_present():
    both = build_data([PRICE_FINDING, SECTOR_FINDING], ["price_history", "sector_performance"])
    assert both["derived"] == {"relative_return_30d": "6.0%"}  # 10% stock - 4% sector

    only_price = build_data([PRICE_FINDING], ["price_history"])
    only_sector = build_data([SECTOR_FINDING], ["sector_performance"])
    assert "derived" not in only_price
    assert "derived" not in only_sector


def test_build_data_missing_covers_errors_and_workers_not_dispatched():
    errored = Finding(source="sector_performance", error="no ETF data")
    data = build_data([PRICE_FINDING, errored], ["price_history", "sector_performance"])
    assert data["missing"] == ["sector_performance: no ETF data", "financials: not dispatched"]
    assert "sector_performance" not in data  # no section for a failed worker


def test_all_errors_returns_fixed_thesis_without_calling_gemini(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "write_thesis", lambda *args: calls.append(args))
    findings = [Finding(source=w, error=f"{w} down") for w in ALL]
    thesis = synthesize(make_state(findings))["thesis"]
    assert calls == []
    assert "No data" in thesis.summary
    assert thesis.bull_points == [] and thesis.bear_points == []
    assert thesis.missing == [f"{w}: {w} down" for w in ALL]


def test_invalid_evidence_keys_are_dropped_with_warning(monkeypatch, caplog):
    generated = Thesis(
        summary="s",
        bull_points=[ThesisPoint(claim="margins", evidence=["financials.gross_margin", "financials.made_up"])],
        bear_points=[ThesisPoint(claim="lag", evidence=["derived.relative_return_30d", "missing"])],
        missing=[],
    )
    monkeypatch.setattr(module, "write_thesis", lambda *args: generated)
    with caplog.at_level("WARNING", logger="advisor.synthesize"):
        thesis = synthesize(make_state([PRICE_FINDING, SECTOR_FINDING, FINANCIALS_FINDING]))["thesis"]
    assert thesis.bull_points[0].evidence == ["financials.gross_margin"]
    assert thesis.bear_points[0].evidence == ["derived.relative_return_30d"]
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 2


def test_gemini_failure_returns_fallback_thesis(monkeypatch):
    def boom(*args):
        raise RuntimeError("Gemini down")

    monkeypatch.setattr(module, "write_thesis", boom)
    thesis = synthesize(make_state([FINANCIALS_FINDING], ["financials"]))["thesis"]
    assert "failed" in thesis.summary
    assert thesis.bull_points == [] and thesis.bear_points == []
    assert thesis.missing == ["price_history: not dispatched", "sector_performance: not dispatched"]


def test_write_thesis_receives_built_data(monkeypatch):
    received = {}

    def fake(user_query, company_name, ticker, data):
        received.update(user_query=user_query, company_name=company_name, ticker=ticker, data=data)
        return Thesis(summary="s", bull_points=[], bear_points=[], missing=[])

    monkeypatch.setattr(module, "write_thesis", fake)
    synthesize(make_state([FINANCIALS_FINDING], ["financials"]))
    assert received["ticker"] == "NVDA"
    assert received["company_name"] == "Nvidia"
    assert received["data"]["financials"]["gross_margin"] == "70.0%"
