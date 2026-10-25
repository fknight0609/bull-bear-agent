# Plan

Planning decisions for the Financial Advisor app. CLAUDE.md holds the rules;
this file holds the decisions behind them, the build order, and open questions.
Update it when a decision changes.

## Status

| Step | State |
|---|---|
| Fetch tools: price history, sector performance, financials | done |
| resolve_ticker tool (CSV lookup) | done |
| parse_query node (Gemini extracts company, resolves ticker, or asks to clarify) | done |
| State schema (`src/state.py`) + CLAUDE.md architecture update | done |
| Minimal graph (`START → parse_query → END`) + debug UI (`app.py` prints final state as JSON) | done |
| dispatch node (`parse_query → dispatch → END`; shared Gemini client in `src/llm.py`) | done, check in debug UI |
| Worker nodes (x3) + fan-out edge after dispatch | next |
| synthesize node + `Thesis` model | not started |
| Reviewer loop | later |
| Deploy: Next.js frontend + FastAPI on Vercel (replaces Streamlit) | later, after synthesize works end to end |
| Supabase database | later, use not decided yet |

## How we build

- **Incrementally, end to end.** Each new node is added to `src/graph.py` and
  checked in the debug UI before the next one is built.
- **The UI only calls `graph.invoke({"user_query": ...})`** and renders the
  final state. It never calls nodes directly, so it doesn't change as the
  graph grows.
- **Each run is independent.** There's no checkpointer, so the graph doesn't
  remember the previous query.
- **Two Claude windows:** one for planning (Opus), one for coding (Sonnet).
  This file is how they stay in sync.

## Architecture

```
parse_query
  ├─ clarifying question / not found / ambiguous ─→ END (UI shows question or candidates)
  └─ resolved ─→ dispatch (Gemini picks workers)
                   ├─→ price_history worker      ─┐
                   ├─→ sector_performance worker ─┼─→ synthesize ─→ END
                   └─→ financials worker         ─┘
                   (any non-empty subset, run in parallel)
```

## Decisions

1. **Dynamic fan-out over a fixed worker set.** Dispatch picks one to three
   workers depending on the query ("Nvidia's margin?" → financials only;
   "should I buy Nvidia?" → all three).
2. **Mandates are worker names only.** No per-worker instructions. That means
   no `Send()`: a conditional edge after dispatch returns a list of node names.
   Instructions only become useful once a worker can act on them (likely with
   the reviewer loop).
3. **Dispatch uses Gemini** with structured output limited to the allowed
   worker names. Gemini chooses tools and never produces figures, so hard
   rule 1 holds.
4. **Workers are deterministic.** No LLM inside a worker: it calls its fetch
   tool and appends a `Finding`. Gemini is used only in parse_query, dispatch
   and synthesize.
5. **Fan-in uses plain edges, not an explicit join.** Each worker → synthesize.
   `add_edge([a, b, c], "synthesize")` would wait for all three and never fire
   when only one was dispatched.
6. **A failed worker doesn't stop the run.** It writes a `Finding` with
   `error` set. synthesize works with what arrived and says what is missing;
   it never fills gaps.
7. **Disambiguation stays in the UI.** `TickerResolution` gains `candidates`
   so the UI has options to show.
8. **Dispatch falls back to all three workers** when Gemini picks none or the
   call fails. The company is already resolved, so a vague question gets the
   full picture rather than another clarifying question.

## State schema (`src/state.py`)

Pydantic `AgentState`. Nodes receive the model instance and return a partial
dict of only the changed keys.

| Field | Type | Writer |
|---|---|---|
| `user_query` | `str` | input |
| `company_name` | `Optional[str]` | parse_query |
| `resolution` | `Optional[TickerResolution]` | parse_query |
| `clarifying_question` | `Optional[str]` | parse_query |
| `mandates_dispatched` | `list[WorkerName]` | dispatch |
| `findings` | `Annotated[list[Finding], operator.add]` | workers |
| `ticker` | read-only property from `resolution` | — |

- `Finding` = `source: WorkerName` + `data` (one of the three tool models)
  **or** `error: str`, never both.
- `WorkerName` = `Literal["price_history", "sector_performance", "financials"]`.
- **Reducer rule:** a key needs a reducer only if several nodes write it in
  the same step. Without one, LangGraph raises `InvalidUpdateError`. Keys
  written in different steps just overwrite. Only `findings` has one.
- No separate stored `ticker`, so it can't drift from `resolution`.
- `thesis` and `review_round` are added when synthesize and the reviewer are
  built.

## Deployment (later)

Target host is **Vercel**. Streamlit can't run there: it needs a long-running
server with a WebSocket per browser, and Vercel runs short-lived functions.

```
Next.js (React) frontend ──HTTP──→ FastAPI (Vercel Python function) ──→ graph.invoke(...)
```

- Keep Streamlit as the local debug UI until synthesize works end to end.
  Building a React UI earlier means reworking it each time the state changes.
- FastAPI exposes one endpoint, roughly `POST /research {query} → final state`.
- `src/` doesn't change (hard rule 3). Only the UI layer is replaced.
- When this starts, update the CLAUDE.md Stack section, which currently says
  Streamlit and "do not substitute without asking".
- Add `requirements.txt` first. The repo has none, and every host needs one.

**Check before committing to Vercel for the backend:**
1. **Function timeout.** A full run makes several Gemini calls plus yfinance
   fetches. Time a real run and compare it with the limit for your Vercel plan.
2. **Bundle size.** pandas, numpy, yfinance and langgraph are large. Try an
   early throwaway deploy to see whether they fit.

**Fallback:** keep the frontend on Vercel and host only the Python API on
Cloud Run or Render. The frontend code stays the same.

## Database (later): Supabase

What it stores isn't decided yet. Candidates:
- **Research history:** past queries and theses per user.
- **Users and auth:** Supabase Auth, if the app gets logins.
- **Graph checkpointer:** Supabase is Postgres, so LangGraph's Postgres
  checkpointer can use it. This is the likely solution for multi-turn
  clarification (see open questions).
- **Fetch cache:** store yfinance results to cut latency and rate-limit risk.

Constraints that carry over: credentials go in `.env`, tests don't make live
Supabase calls, and database access sits in its own module, not scattered
through the nodes.

## Open questions

- **synthesize:** the `Thesis` model shape. Where cross-source arithmetic
  (e.g. stock return minus sector return) lives: in state if the UI shows it,
  otherwise inside synthesize. Either way it is computed in Python (rule 2).
- **Reviewer loop (later):** a `review_round` cap of 1–2. On a re-run,
  `operator.add` keeps the old finding next to the new one. Decide whether
  that's wanted, or use a reducer that replaces findings by `source`.
- **Multi-turn clarification:** answering a clarifying question and resuming
  needs a checkpointer and a `thread_id`. Not needed yet.
