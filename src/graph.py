"""Wires nodes into the LangGraph graph."""

from langgraph.graph import END, START, StateGraph

from src.nodes.parse_query import parse_query
from src.state import AgentState


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_query", parse_query)
    builder.add_edge(START, "parse_query")
    builder.add_edge("parse_query", END)
    return builder.compile()


graph = build_graph()
