"""Wires nodes into the LangGraph graph."""

from langgraph.graph import END, START, StateGraph

from src.nodes.dispatch import dispatch
from src.nodes.parse_query import parse_query
from src.state import AgentState


def route_after_parse(state: AgentState) -> str:
    """Go on to dispatch only when a single ticker was resolved; otherwise end for the UI."""
    if state.clarifying_question is None and state.resolution and state.resolution.is_present == "yes":
        return "dispatch"
    return END


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_query", parse_query)
    builder.add_node("dispatch", dispatch)
    builder.add_edge(START, "parse_query")
    builder.add_conditional_edges("parse_query", route_after_parse, ["dispatch", END])
    builder.add_edge("dispatch", END)  # replaced by the fan-out to workers once they exist
    return builder.compile()


graph = build_graph()
