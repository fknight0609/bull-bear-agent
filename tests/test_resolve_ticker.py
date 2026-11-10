from src.tools.resolve_ticker import resolve_ticker


def test_exact_match():
    result = resolve_ticker("Apple Inc")
    assert result.is_present == "yes"
    assert result.ticker == "AAPL"
    assert result.candidates == []


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


def test_ambiguous_result_has_sorted_candidates():
    result = resolve_ticker("Apple")
    assert len(result.candidates) > 1
    assert result.candidates == sorted(result.candidates)
    assert all("apple" in name.lower() for name in result.candidates)


def test_not_present():
    result = resolve_ticker("Some Nonexistent Company")
    assert result.is_present == "no"
    assert result.ticker is None
    assert result.candidates == []


def test_empty_input_is_not_present():
    result = resolve_ticker("   ")
    assert result.is_present == "no"
    assert result.ticker is None


def write_csv(tmp_path, rows):
    path = tmp_path / "tickers.csv"
    path.write_text("company,ticker\n" + "\n".join(f"{c},{t}" for c, t in rows) + "\n", encoding="utf-8")
    return path


def test_whole_word_prefix_beats_substring(tmp_path):
    path = write_csv(tmp_path, [("Ford Motor Company", "F"), ("Ashford Hospitality Trust", "AHT")])
    result = resolve_ticker("Ford", data_path=path)
    assert result.is_present == "yes"
    assert result.ticker == "F"


def test_whole_word_anywhere_beats_substring(tmp_path):
    path = write_csv(tmp_path, [("Ford Motor Company", "F"), ("Motorola Solutions", "MSI"), ("Automotive Parts", "AUTO")])
    result = resolve_ticker("motor", data_path=path)
    assert result.is_present == "yes"
    assert result.ticker == "F"


def test_falls_back_to_substring_when_no_whole_word_match(tmp_path):
    path = write_csv(tmp_path, [("Pineapple Financial", "PAPL"), ("Maui Land", "MLP")])
    result = resolve_ticker("apple", data_path=path)
    assert result.is_present == "yes"
    assert result.ticker == "PAPL"


def test_several_whole_word_prefix_matches_are_ambiguous(tmp_path):
    path = write_csv(tmp_path, [("Alphabet Inc Class A", "GOOGL"), ("Alphabet Inc Class C", "GOOG"), ("Alphabetical Co", "ALP")])
    result = resolve_ticker("Alphabet", data_path=path)
    assert result.is_present == "ambiguous"
    assert result.candidates == ["Alphabet Inc Class A", "Alphabet Inc Class C"]


def test_query_with_regex_characters_is_literal(tmp_path):
    path = write_csv(tmp_path, [("AT&T Inc.", "T"), ("Other Co", "OTH")])
    assert resolve_ticker("at&t (", data_path=path).is_present == "no"
    assert resolve_ticker(".*", data_path=path).is_present == "no"
