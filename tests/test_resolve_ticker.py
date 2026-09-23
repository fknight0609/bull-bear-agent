from src.tools.resolve_ticker import resolve_ticker


def test_exact_match():
    result = resolve_ticker("Apple Inc")
    assert result.is_present == "yes"
    assert result.ticker == "AAPL"


def test_case_insensitive_and_whitespace():
    result = resolve_ticker("  microsoft corporation  ")
    assert result.is_present == "yes"
    assert result.ticker == "MSFT"


def test_substring_match():
    result = resolve_ticker("Tesla")
    assert result.is_present == "yes"
    assert result.ticker == "TSLA"


def test_ambiguous_when_multiple_companies_match():
    result = resolve_ticker("Apple")
    assert result.is_present == "ambiguous"
    assert result.ticker is None


def test_not_present():
    result = resolve_ticker("Some Nonexistent Company")
    assert result.is_present == "no"
    assert result.ticker is None


def test_empty_input_is_not_present():
    result = resolve_ticker("   ")
    assert result.is_present == "no"
    assert result.ticker is None
