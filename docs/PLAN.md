# Plan

Planning decisions for the Financial Advisor app. CLAUDE.md holds the rules;
this file holds the decisions behind them, the build order, and open questions.
Update it when a decision changes.

## Status

| Step | State |
|---|---|
| Fetch tools: price history, sector performance, financials | done |
| resolve_ticker tool (CSV lookup) | done |
| Ticker data: ~6.4k US + UK listings (`scripts/build_tickers.py`) and ranked name matching in `resolve_ticker` | done |
| parse_query node (Gemini extracts company, resolves ticker, or asks to clarify) | done |
| State schema (`src/state.py`) + CLAUDE.md architecture update | done |
| Minimal graph (`START → parse_query → END`) + debug UI (`app.py` prints final state as JSON) | done |
| dispatch node (Gemini picks workers; shared Gemini client in `src/llm.py`) | done, run live locally in the debug UI |
| Worker nodes (x3) + fan-out edge after dispatch | done, run live locally in the debug UI |
| synthesize node + `Thesis` model | done, run live locally in the debug UI |
| Reviewer loop | next |
| FastAPI endpoint (`api/index.py`: `GET /health`, `POST /research`), run locally with uvicorn + curl | done, tests in `tests/test_api.py`; a live run hit Gemini 503s and a hang before the timeout was added (decision 15) |
| Gemini client timeout and retry (`src/llm.py`), model `gemini-3.1-flash-lite` | done, live run through the API worked |
| Model fallback on retry | backlog |
| `requirements.txt` (runtime) and `requirements-dev.txt`, `pytest.ini` | done |
| Vercel config (`vercel.json` with `maxDuration` 100, `.vercelignore`) | written, not yet deployed |
| Preview deploy to Vercel (`vercel deploy`, not `--prod`) | next |
| Next.js frontend (replaces Streamlit for users) | later |
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
9. **`Thesis` shape.** `summary` (answers the user's question first), then
   `bull_points` and `bear_points`, each a `ThesisPoint` (`claim` plus
   `evidence`: keys like `financials.gross_margin` or
   `derived.relative_return_30d`), and `missing` (what was unavailable). No
   buy/sell instruction. Evidence keys make every claim traceable to the data
   dict, so rule 1 can be checked rather than trusted.
10. **Cross-source arithmetic lives inside synthesize, not in state.**
    `build_data` (pure Python, rule 2) formats fractions as percentage strings,
    rounds the rest, and adds a `derived` section (currently
    `relative_return_30d` = stock minus sector 30-day return, only when both
    were fetched). The data dict goes to Gemini and is not stored in state, since the UI
    doesn't show it. Move it into state if a UI ever needs it.
11. **synthesize never crashes the run, and checks Gemini's output.** Evidence
    keys not present in the data dict are dropped with a warning. With no
    successful finding it returns a fixed "no data" thesis and does not call
    Gemini. If Gemini fails it returns a thesis whose summary says synthesis
    failed. `build_data(findings, mandates_dispatched)` builds the `missing`
    list (errored workers with the message, plus workers that weren't
    dispatched). The fallback theses use it as is; on the normal path Gemini
    writes `Thesis.missing` from it and could omit an item. A point whose
    evidence keys are all dropped is kept with empty `evidence`.
12. **Ticker matching is ranked, not plain substring.** `resolve_ticker` tries
    three tiers and uses only the best non-empty one: the name starts with the
    query as a whole word ("Ford" → Ford Motor, not Ashford), then the query
    as a whole word anywhere, then plain substring. Several matches in the
    chosen tier are `ambiguous` with `candidates`, so "Apple" and "Alphabet"
    still ask which one. Substring-only matching was fine for 18 rows but made
    "Meta", "Visa" and "Intel" ambiguous once the list grew.
13. **Ticker data is generated, not hand-edited.** `src/tools/data/tickers.csv`
    (`company,ticker,exchange`) is rebuilt by `scripts/build_tickers.py` from
    NASDAQ Trader's symbol directory (US common equity only: no ETFs, test
    symbols, warrants, rights, preferreds, notes or units) and the FTSE 100,
    FTSE 250 and FTSE SmallCap tables on Wikipedia (UK). Tickers are in Yahoo
    Finance form, which is what the fetch tools use: `BRK-B`, `HSBA.L`. Names
    that would collide get the ticker appended, e.g. `Berkshire Hathaway Inc.
    (BRK-B)`.

14. **The API layer is a thin adapter.** `api/index.py` only turns HTTP into
    `graph.invoke({"user_query": ...})` and the validated `AgentState` back
    into JSON (`model_dump(mode="json")`, the same state the debug UI shows).
    No business logic, and `src/` is unchanged.
    - **Sync request first.** `POST /research` blocks until the run finishes
      (a plain `def`, so FastAPI runs it in a threadpool). Streaming and
      job + poll stay as later steps (see Deployment).
    - **Errors are hidden from clients.** Any exception is logged server-side
      with the traceback, and the client gets 500 `{"detail": "Research
      failed"}`. For local debugging only, `EXPOSE_ERRORS=1` adds an `error`
      field with `ExceptionType: message`. It is off by default and must not
      be set on a deployment.
    - **Input is validated at the edge.** `query` is stripped and must be 1–500
      characters, otherwise 422.
    - **CORS comes from the environment.** `ALLOWED_ORIGINS` (comma-separated,
      default `http://localhost:3000`), GET and POST only.
    - **Logging uses `logging.basicConfig` at INFO**, so the `advisor` lines
      (including run duration) show under uvicorn and in Vercel function logs.
15. **Gemini calls have a timeout and one retry; the function limit is 100 s.**
    The first live runs hit `503 UNAVAILABLE` ("high demand") from
    `gemini-3.8-flash` and one request hung for minutes, because the client had
    no timeout. `src/llm.py` now sets a 20 s timeout per request and 2 attempts
    (one retry; the SDK retries 408, 429 and 5xx with backoff). A run makes
    about three sequential calls, so the worst case is roughly 3 × 2 × 20 s plus
    backoff. That can pass 100 s only if every call hangs, and then Vercel ends
    the function at `maxDuration` 100 (`vercel.json`), down from the earlier 300
    s. A normal run is expected to be ~10–40 s (not yet timed live). Retry
    attempts are not counted per run in the logs. The model was then switched
    to `gemini-3.1-flash-lite`, and a live run through the API worked. Falling
    back to another model on retry is in the Backlog.

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
| `thesis` | `Optional[Thesis]` | synthesize |
| `ticker` | read-only property from `resolution` | — |

- `Finding` = `source: WorkerName` + `data` (one of the three tool models)
  **or** `error: str`, never both.
- `WorkerName` = `Literal["price_history", "sector_performance", "financials"]`.
- **Reducer rule:** a key needs a reducer only if several nodes write it in
  the same step. Without one, LangGraph raises `InvalidUpdateError`. Keys
  written in different steps just overwrite. Only `findings` has one.
- No separate stored `ticker`, so it can't drift from `resolution`.
- `review_round` is added when the reviewer is built.

## Deployment

Target host is **Vercel**. The API layer and the Vercel config exist (decision
14, `vercel.json`, `.vercelignore`); nothing is deployed yet. Streamlit can't run there: it needs a long-running
server with a WebSocket per browser, and Vercel runs short-lived functions.

```
Next.js (React) frontend ──HTTP──→ FastAPI (Vercel Python function) ──→ graph.invoke(...)
```

- Keep Streamlit as the local debug UI until synthesize works end to end.
  Building a React UI earlier means reworking it each time the state changes.
- **Why FastAPI.** The Next.js frontend runs JavaScript and can't run the
  Python graph, and `GEMINI_API_KEY` must stay server-side. FastAPI is a thin
  HTTP layer: `POST /research {query}` → `graph.invoke({"user_query": query})`
  → final state as JSON. It holds no business logic, and `src/` is unchanged.
  The Pydantic state serialises directly. Any Python HTTP handler would work;
  FastAPI was chosen for native Pydantic, Vercel Python support, local
  `uvicorn` runs and the `/docs` page.
- `src/` doesn't change (hard rule 3). Only the UI layer is replaced.
- The CLAUDE.md Stack section now lists FastAPI (`api/index.py`) as the HTTP
  layer for deploys and Streamlit as the local debug UI.
- `requirements.txt` (runtime only, pinned) and `requirements-dev.txt` exist.
- `vercel.json` rewrites all paths to `api/index.py` and sets `maxDuration` to
  100 with `includeFiles: "src/**"`, so `tickers.csv` and the prompt files are
  bundled. `.vercelignore` excludes tests, scripts, `src/temp/`, `app.py`,
  `.env`, `.venv`, `__pycache__` and `docs/`. The root `app.py` is Streamlit,
  so the explicit `api/index.py` entrypoint is kept even if Vercel's zero-config
  FastAPI detection would work without `vercel.json` (unchecked).
- Env vars `GEMINI_API_KEY` and `ALLOWED_ORIGINS` are set in the Vercel
  project, never in files. `EXPOSE_ERRORS` must not be set there.

**Check before committing to Vercel for the backend:**
1. **Function timeout.** Limits per the Vercel docs (checked 2026-11-18):
   Hobby 300 s default and max; Pro/Enterprise 300 s default, 800 s max
   (1800 s in beta). We set 100 s on purpose (decision 15). A run is expected
   to take ~10–40 s (not yet timed live). The Hobby plan is for
   non-commercial use only.
2. **Bundle size.** pandas, numpy, yfinance and langgraph are large. Try an
   early throwaway deploy to see whether they fit.

**Fallback:** keep the frontend on Vercel and host only the Python API on
Cloud Run or Render. The frontend code stays the same.

**Request model, in order:**
1. Synchronous `POST /research` first.
2. Add streaming via `graph.stream()` if waiting with no feedback feels bad.
   This is still one request.
3. Async job + poll only if runs approach the limit (e.g. a reviewer loop with
   many rounds).

Vercel has no always-on workers. Vercel Workflows/Queues exist, but their
Python support is unverified. If real workers are needed, use Cloud Run or
Render.

**Risk:** the Gemini free-tier quota (~20 requests/day, ~3–4 per run) and
yfinance rate limits from cloud IPs will likely bind before any Vercel limit.
Gemini capacity errors (503) have already been seen locally; retries only
help for short spikes.

## Database (later): Supabase

Supabase is one Postgres database. "Vector" means the optional `pgvector`
extension in that same database, not a separate DB. It isn't needed now. It
would only be for semantic search over past theses or documents (RAG) later.

What it stores isn't fully decided. Candidates:
- **Research history (first use):** past queries and theses. Sketch of a
  `runs` table:

  | Column | Type | Note |
  |---|---|---|
  | `id` | uuid | primary key |
  | `user_query` | text | |
  | `ticker` | text | |
  | `thesis` | jsonb | the `Thesis` model |
  | `findings` | jsonb | optional |
  | `created_at` | timestamptz | |
  | `user_id` | uuid | later, with Supabase Auth |

- **Users and auth:** Supabase Auth, if the app gets logins.
- **Graph checkpointer:** LangGraph's Postgres checkpointer can use Supabase.
  This is separate from run history: `runs` holds finished results, while the
  checkpointer holds mid-run state. It is only needed for multi-turn
  clarification (see open questions), later.
- **Fetch cache:** store yfinance results to cut latency and rate-limit risk.

Constraints that carry over: credentials go in `.env`, tests don't make live
Supabase calls, and database access sits in its own module, not scattered
through the nodes.

## Backlog

- **API key on `POST /research` (removed, re-add later).** The production URL
  is publicly reachable (Deployment Protection doesn't cover it) and every
  call uses Gemini quota. An `X-API-Key` header check, compared in constant
  time against an `API_KEY` env var, was built and then taken out for now.
  Re-add it before the URL is shared. Fail closed (503) when `API_KEY` is
  unset, so a deploy without the key isn't open. The key must be random, not
  derived from the repo owner or project name (the repo is public).

- **UI redo, then public sharing.** The current UI isn't ready to show. Do
  these with it, before the URL goes on a resume or LinkedIn:
  - Per-IP rate limit or daily request cap in `api/index.py`.
  - A "not financial advice" disclaimer, and a note that figures come from
    yfinance (unofficial, possibly stale).
  - A landing route or frontend at `/` (the bare URL returns 404 today).
  - Confirm the Gemini key has no billing attached, or use a dedicated key.
  - Decide how a frontend holds the API key. A key in browser JavaScript is
    public, so a real frontend should call the API through its own server-side
    route.
  - Check git history for committed secrets before linking the repo.

- **Model fallback on retry (not built).** Today a retry repeats the same
  model, so an overloaded model fails both attempts (seen with
  `gemini-3.8-flash`: 503s, then 504 `DEADLINE_EXCEEDED` twice). Instead, when
  a call fails with a retryable error (timeout, 408, 429, 5xx), retry on the
  next model in an ordered list. Sketch:
  - One helper in `src/llm.py` wraps `generate_content`. The three nodes call
    it instead of `client().models.generate_content`, and `MODEL` becomes an
    ordered `MODELS` list (e.g. `gemini-3.1-flash-lite`, then `gemini-3.7-flash`
    or another Flash model; to be picked and tested).
  - Fall back only on retryable errors. Bad requests and auth errors (400, 401,
    403) fail at once, since another model won't fix them.
  - Keep the total inside the 100 s function limit: one attempt per model with
    the 20 s timeout, and a cap on how many models to try per call.
  - Log which model answered and why it fell back. Every model in the list must
    support structured JSON output (`response_schema`), which the nodes use.
  - Check how the free-tier quota counts across models before relying on it.
  - Tests with a fake client; no live calls.

## Open questions

- **Run time:** `POST /research` now completes locally with
  `gemini-3.1-flash-lite`, but the run time hasn't been recorded, so whether
  100 s is enough is unmeasured. Check the `Graph invoke took` log line.
- **Vercel preview deploy:** untested. Bundle size (pandas, numpy, yfinance,
  langgraph), whether `includeFiles` picks up the data files, and zero-config
  detection need a throwaway preview to confirm. Deployment Protection on
  previews returns 401 until bypassed.
- **Python version on Vercel:** the venv is 3.13 and CLAUDE.md says 3.12+. No
  version is pinned for the deployment yet.
- **Test runner:** `pytest.ini` sets `pythonpath = .` so bare `pytest` and
  `python -m pytest` both work.

- **Ticker coverage:** UK is FTSE 100/250/SmallCap only (about 430 names, and
  the SmallCap table is partial), not every LSE listing. No free official UK
  list was found. yfinance coverage of every ticker is unchecked.
- **Aliases:** the lookup matches company names only, so "Google" (Alphabet)
  and "AMD" (Advanced Micro Devices) don't resolve. Needs an alias list or a
  Gemini suggestion checked against the CSV.
- **Dual listings:** a company listed in both the US and UK ("Shell", "HSBC",
  "AstraZeneca") comes back `ambiguous`. Decide whether to prefer the US line,
  or ask the user.
- **Exchange codes:** 10 rows have an unidentified exchange code in the NASDAQ
  Trader file and are labelled `US`. The column isn't used by the resolver.
- **Reviewer loop (later):** a `review_round` cap of 1–2. On a re-run,
  `operator.add` keeps the old finding next to the new one. Decide whether
  that's wanted, or use a reducer that replaces findings by `source`.
- **Multi-turn clarification:** answering a clarifying question and resuming
  needs a checkpointer and a `thread_id`. Not needed yet.
