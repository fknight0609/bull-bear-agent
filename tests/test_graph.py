from src.graph import graph
from src.nodes import parse_query as module


def test_graph_resolves_company_end_to_end(monkeypatch):
    monkeypatch.setattr(module, "extract_companies", lambda user_query: ["Nvidia"])
    result = graph.invoke({"user_query": "Tell me about Nvidia"})
    assert result["resolution"].is_present == "yes"
    assert result["resolution"].ticker == "NVDA"
