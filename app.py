import logging

import streamlit as st

from src.graph import graph
from src.state import AgentState


class ListHandler(logging.Handler):
    """Collects formatted log lines so they can be shown in the sidebar."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


log = logging.getLogger("advisor")
log.setLevel(logging.INFO)

text = st.text_input("Query")

if st.button("Run"):
    handler = ListHandler()
    log.addHandler(handler)
    try:
        log.info("Graph invoked: user_query=%r", text)
        result = graph.invoke({"user_query": text})
        state = AgentState.model_validate(result).model_dump(mode="json")
        log.info("Graph finished. Final state: %s", state)
        st.json(state)
    except Exception as e:
        log.exception("Graph failed")
        st.exception(e)
    finally:
        log.removeHandler(handler)
        with st.sidebar:
            st.subheader("Debug log")
            st.code("\n".join(handler.lines), language="text", wrap_lines=True)
