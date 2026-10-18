# ConvergeMind

**A memory immune system for agent teams: evidence-backed context, safe handoffs, and automatic revalidation when what an agent "knows" changes.**

Built for [Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb) — **Track 2: Agent Memory and Coordination**.

---

## The problem

Every support team has the same failure: you explain your problem to a chat agent, get handed to email, and explain it again. The usual fix is to stuff a transcript into the next agent's context window, which does not scale past a few sessions and does nothing at all for the agent serving a *different* customer with the *same* problem.

ConvergeMind puts the memory in a graph instead of in a context window. Two agents, `ChatAgent` and `EmailAgent`, run as separate invocations with separate, empty context windows. They pass each other no transcript. Everything one knows about the other's work it learned by traversing FalkorDB.

That alone is not enough for a real agent fleet: stale, contradictory, and malicious memories should not quietly become instructions. ConvergeMind treats remembered information as a governed **claim** with evidence, trust, status, and downstream dependencies. The Memory Guardian can quarantine an untrusted write, expose a conflict, and calculate the blast radius when newly verified evidence supersedes an old claim.

## Remove FalkorDB and nothing works

This is deliberate, and it is the test the hackathon rules actually set. There is no cache, no in-memory fallback, no secondary store. Every agent tool is a Cypher query:

| Tool | What it does | Memory type |
|---|---|---|
| `recall_customer_context` | Every past session, who handled it, every known fact, every past issue | episodic + semantic |
| `record_fact` | Store a durable fact, with provenance to the session that learned it | semantic |
| `log_resolution` | Record a fix, in the customer's history *and* the shared knowledge graph | procedural |
| `find_similar_resolutions` | How has this issue been fixed before, **for anyone** | procedural, cross-tenant |
| `known_issue_types` | Every issue category the shared graph has seen | procedural |

All five live in [`backend/memory_tools.py`](backend/memory_tools.py). The agent is instructed to call `recall_customer_context` before it says a single word, because with an empty context window it genuinely knows nothing else.

## Data model

```
Per-customer graph key  →  customer:{id}
──────────────────────────────────────────────────────────────
  (Customer)-[:HAD_SESSION]->(Session)-[:HANDLED_BY]->(Agent)
  (Session)-[:NEXT]->(Session)                    episodic ordering
  (Session)-[:RAISED]->(Issue)
  (Customer)-[:HAS_FACT]->(Fact)<-[:LEARNED]-(Session)   provenance
  (Session)-[:ASSERTED]->(MemoryClaim)<-[:SUPPORTS]-(Evidence)
  (Decision)-[:DEPENDS_ON]->(MemoryClaim)-[:CAPTURED_IN]->(HandoffCapsule)
  (MemoryClaim)-[:CONTRADICTS|SUPERSEDES]->(MemoryClaim)

Shared graph key  →  shared:knowledge
──────────────────────────────────────────────────────────────
  (Resolution)-[:APPLIES_TO]->(IssueType)
```

Three memory types, three different shapes in the graph:

- **Episodic** is the `:NEXT` chain of sessions. What happened, in order.
- **Semantic** is `(Customer)-[:HAS_FACT]->(Fact)`, with a `:LEARNED` edge back to the session that discovered it, so the UI can show *which agent* found each fact.
- **Procedural** is `(Resolution)-[:APPLIES_TO]->(IssueType)` in the **shared** graph. A fix learned while helping Carol is retrievable by the agent helping Bob, and that retrieval is a graph traversal, not a text search.

### Memory immunity

A memory claim moves through `proposed`, `verified`, `disputed`, `superseded`, or `quarantined` states. Only verified claims are eligible for an agent's recalled context or handoff capsule.

- **Provenance:** Every claim is asserted by a session and supported by evidence with a source type and trust score.
- **Quarantine:** Low-trust external material is retained for audit but excluded from agent context.
- **Conflict:** Contradictory claims remain explicit graph relationships instead of being silently overwritten.
- **Blast radius:** When a verified claim supersedes an older one, every `Decision` or `HandoffCapsule` that depended on the stale claim is marked `needs_revalidation`.

The UI's **Memory Guardian** rail demonstrates both cases: it can inject an untrusted recovery instruction and quarantine it, or introduce new verified carrier evidence that invalidates an earlier password-reset decision.

### Graph separation is a keyspace, not a WHERE clause

Each customer gets their own FalkorDB graph key (`customer:cust_alice`). A query running in one tenant's graph physically cannot traverse into another's. There is no filter to forget and no predicate to get wrong.

The agent tool schemas also **do not accept a `customer_id`**. The server binds it from the current request ([`backend/agent.py:_dispatch_for`](backend/agent.py)). If the model hallucinates another customer's id, or a prompt injection tells it to fetch one, the bound dispatch ignores it. `tests/test_isolation.py` checks this model-to-tool boundary with a hostile argument.

**This is graph-level separation, not end-to-end tenant authorization.** The FastAPI endpoints currently have no login or authentication, and accept `customer_id` from the caller. Anyone who can reach the API can choose a seeded customer ID and access that customer's graph. The demo uses fabricated data only; do not put real customer data in it or present this build as production-secure multi-tenant software. A production deployment needs authenticated identity and server-side tenant binding before exposing customer data.

## Test suite

Run the database-backed suite with FalkorDB available at the configured host:

```
$ python -m pytest
```

- `tests/test_memory_tools.py` — all three memory types, handoff chaining, fact provenance, cross-customer reuse
- `tests/test_isolation.py` — one tenant cannot read another, and the model cannot steer a tool across the boundary
- `tests/test_concurrency.py` — 50 concurrent retrievals lose zero increments; 30 tenants written in parallel show zero bleed
- `tests/test_agent.py` — tool dispatch, bounded tool loop, error recovery
- `tests/test_api.py` — every endpoint
- `tests/test_memory_guardian_sandbox.py` — randomized, database-free blast-radius checks for claim supersession and revalidation

### Concurrency proof you can run on camera

```
$ python -m scripts.concurrency_test

1. 200 concurrent retrievals of one shared resolution
   workers            : 16
   reuse_count        : 201
   expected           : 201
   lost updates       : 0
   -> PASS, no lost writes

2. 100 tenants written concurrently, checked for bleed
   graph keys written : 100
   cross-tenant bleed : 0
   -> PASS, every tenant isolated
```

The increment is a single Cypher `SET r.reuse_count = r.reuse_count + 1`, which FalkorDB applies atomically per query. A lost update would show up immediately as a short count.

## Run it

**Prerequisites:** Docker, Python 3.10+, and a [Groq API key](https://console.groq.com) (free tier).

```bash
git clone <this repo> && cd ConvergeMind
cp .env.example .env          # add your GROQ_API_KEY
pip install -r requirements.txt

docker compose up -d          # FalkorDB on :6379, FalkorDB Browser on :3000
python -m backend.seed_data   # 4 synthetic customers with fabricated history

uvicorn backend.api:app --reload --port 8000     # terminal 1
streamlit run ui/streamlit_app.py                # terminal 2  -> :8501
```

Then open <http://localhost:8501>, pick `cust_bob`, and tell `ChatAgent` *"I'm locked out of my account again."* It will recall that Bob cannot receive SMS codes abroad, look up how that was solved before, and send an email reset link instead. Hand off to `EmailAgent` and ask what happened: it reads the graph and tells you, having been given no transcript.

For the full memory-immunity flow, use **simulate verified change** in the Memory Guardian rail, then verify the proposed claim. The previous `known_blocker` claim is superseded and every decision that depended on it is visibly flagged for revalidation.

Inspect the raw graph yourself at <http://localhost:3000> (FalkorDB Browser) and run Cypher against `customer:cust_bob` directly.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Graph database | **FalkorDB** | The memory. Multi-graph keying gives per-tenant isolation for free. |
| Agent tier | Groq (`openai/gpt-oss-120b`) | Free tier, and the fastest inference available, which matters when a demo waits on it. Swap via `GROQ_MODEL`. |
| API | FastAPI | Thin; every endpoint is a pass-through to a Cypher-backed tool. |
| UI | Streamlit + vis-network | Three rails: two agents and the live graph. |
| Tests | pytest + Playwright | 30 unit/integration tests, plus render verification at 390/768/1440px. |

## Project layout

```
backend/
  db.py            FalkorDB connection; the tenant-isolation boundary
  schema.py        Idempotent index setup
  memory_tools.py  The five Cypher-backed agent tools  <-- the core
  agent.py         ChatAgent / EmailAgent personas, bound tool dispatch
  api.py           HTTP surface
  seed_data.py     Synthetic demo history
ui/
  streamlit_app.py Three-rail demo UI
  theme.py         Design tokens (the only place a hex literal lives)
  styles.py        Injected CSS
  graph_view.py    Force-directed graph render
scripts/
  concurrency_test.py  Live concurrency proof
  verify_ui.py         Playwright render gate
```

## Data

All demo data is **synthetic and fabricated** (`backend/seed_data.py`), per the hackathon's data rules. No scraped, real, or login-protected data is used anywhere.

## AI assistance disclosure

Per the hackathon's disclosure rule, stated plainly: this project was built with AI assistance. Claude Code and Codex were used as development assistants for implementation and review, and the in-product agents run on Groq-hosted models via tool-calling. The architecture, graph model, and memory-governance design are documented in this repository; the supplied test suite makes the behavioural claims inspectable.

## Licence

MIT
