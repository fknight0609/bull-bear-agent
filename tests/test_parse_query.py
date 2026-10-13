import pytest

from src.nodes import parse_query as module
from src.nodes.parse_query import parse_query


@pytest.fixture
def stub(monkeypatch):
    """Stub Gemini: `companies` is what extraction returns; asked questions are recorded."""
    calls: list[dict] = []

    def _stub(companies: list[str]) -> list[dict]:
        monkeypatch.setattr(module, "extract_companies", lambda user_query: companies)

        def fake_ask(user_query, reason, options):
            calls.append({"reason": reason, "options": options})
            return "QUESTION"

        monkeypatch.setattr(module, "ask_clarifying_question", fake_ask)
        return calls

    return _stub


def test_resolved_company_asks_nothing(stub):
    calls = stub(["Tesla"])
    result = parse_query({"user_query": "What do you think of Tesla stock?"})
    assert result["company_name"] == "Tesla"
    assert result["resolution"].ticker == "TSLA"
    assert result["clarifying_question"] is None
    assert calls == []


def test_ticker_ambiguity_is_passed_through_without_question(stub):
    calls = stub(["Apple"])
    result = parse_query({"user_query": "Is Apple a buy?"})
    assert result["resolution"].is_present == "ambiguous"
    assert result["clarifying_question"] is None
    assert calls == []


def test_ticker_not_found_is_passed_through_without_question(stub):
    calls = stub(["Some Nonexistent Company"])
    result = parse_query({"user_query": "Thoughts on Some Nonexistent Company?"})
    assert result["resolution"].is_present == "no"
    assert result["clarifying_question"] is None
    assert calls == []


def test_no_company_mentioned_asks_which(stub):
    calls = stub([])
    result = parse_query({"user_query": "What's the weather?"})
    assert result["company_name"] is None
    assert result["clarifying_question"] == "QUESTION"
    assert calls[0]["options"] == []


def test_multiple_companies_asks_to_pick_one(stub):
    calls = stub(["Tesla", "Microsoft"])
    result = parse_query({"user_query": "Tesla or Microsoft?"})
    assert result["company_name"] is None
    assert result["clarifying_question"] == "QUESTION"
    assert calls[0]["options"] == ["Tesla", "Microsoft"]
