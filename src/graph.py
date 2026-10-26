"""Wires nodes into the LangGraph graph."""

from typing import get_args

from langgraph.graph import END, START, StateGraph

from src.nodes.dispatch import dispatch
from src.nodes.financials import financials
from src.nodes.parse_query import parse_query
from src.nodes.price_history import price_history
from src.nodes.sector_performance import sector_performance
from src.state import AgentState, WorkerName

WORKERS = {"price_history": price_history, "sector_performance": sector_performance, "financials": financials}
assert set(WORKERS) == set(get_args(WorkerName))  # node names must equal the WorkerName literals


def route_after_parse(state: AgentState) -> str:
    """Go on to dispatch only when a single ticker was resolved; otherwise end for the UI."""
    if state.clarifying_question is None and state.resolution and state.resolution.is_present == "yes":
        return "dispatch"
    return END


def route_after_dispatch(state: AgentState) -> list[WorkerName]:
    """Fan out to exactly the workers dispatch chose."""
    return state.mandates_dispatched


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_query", parse_query)
    builder.add_node("dispatch", dispatch)
    for name, node in WORKERS.items():
        builder.add_node(name, node)
    builder.add_edge(START, "parse_query")
    builder.add_conditional_edges("parse_query", route_after_parse, ["dispatch", END])
    builder.add_conditional_edges("dispatch", route_after_dispatch, list(WORKERS))
    for name in WORKERS:
        builder.add_edge(name, END)  # these become edges to "synthesize" once it exists
    return builder.compile()


graph = build_graph()
