# Social-Agent Engine

**Privacy-aware, long-context conversational agent prototype** — a reproducible Python project for exploring long-term user preference memory, context-window baselines, cost-aware model routing, bounded tools, streaming chat, and evaluation.

> **Status: v0.1 research MVP.** This project does not claim production scale, benchmark improvements, fine-tuning, semantic vector search, LangGraph, knowledge-graph reasoning, or real chatbot quality in offline mode. Those are future experiments, not implemented features.

## Architecture

```text
                   POST /v1/chat or /v1/chat/stream
                                  |
                             FastAPI API
                                  |
                       Auth check (optional key)
                                  |
                     Route (rule-based baseline)
                          /              \
                   Explicit tool       LLM / mock
                  (calc, UTC time)        |
                                     Context assembly
                                     /             \
                              Recent N messages   Opt-in facts
                                  (SQLite)       (SQLite)
                                     \             /
                                   Prompt builder
                                         |
                              OpenAI-compatible API
                               or offline DemoModel
                                         |
                          SSE stream + persisted messages
                                         |
                               Evaluation / load test
```

The *short-term* layer reads the last `N` messages from the current thread. The *long-term* layer stores only explicit `remember: key=value` facts and a very narrow automatically extracted pet-preference example, **when the user has opted in**. Facts are upserted by `(user_id, key)`, which supports preference correction; retrieval is simple lexical ranking. This is a transparent deterministic baseline—not embedding/vector search.

The model route is also a transparent heuristic (small vs large tier), not a learned classifier. Tools are invoked using explicit `@calc` or `@time` commands; the model does not autonomously plan or choose tools. The engine implements readable state transitions and can be compared with LangGraph later.

## Quick start

**Requirements:** Python 3.11+

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
uvicorn social_agent.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** for the browser chat UI, or **http://127.0.0.1:8000/docs** for Swagger. **Default mode is offline:** the deterministic demo model is not a real LLM.

To run with an OpenAI-compatible provider:

```bash
export MODEL_BACKEND=openai
export OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
export OPENAI_COMPAT_API_KEY='your-key'
export SMALL_MODEL='gpt-4o-mini'
export LARGE_MODEL='gpt-4o'
export SOCIAL_AGENT_API_KEY='set-a-strong-local-api-key'
uvicorn social_agent.api:app --host 127.0.0.1 --port 8000
```

The environment examples specify API conventions, not a guaranteed provider/model availability. No credentials should be committed.

## Test the long-term memory behavior

```bash
# Explicit opt-in: this is OFF by default.
curl -X PUT http://127.0.0.1:8000/v1/users/alice/consent \
  -H 'Content-Type: application/json' -d '{"enabled":true}'

curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"alice","thread_id":"one","message":"我喜欢猫"}'

# This can recall the preference from a *different* thread:
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"alice","thread_id":"two","message":"我喜欢什么宠物？"}'

# Preference correction/upsert:
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"alice","thread_id":"three","message":"我现在更喜欢狗"}'

# Delete all user data (history + memories):
curl -X DELETE http://127.0.0.1:8000/v1/users/alice
```

If `SOCIAL_AGENT_API_KEY` is set, add `-H 'X-API-Key: ...'` to protected API calls. The UI offers an API-key field too. The key is a **single shared demo secret**, not per-user authentication.

Other examples: `记住：favorite_drink=tea` or `remember: color=blue`, `@calc (6+4)*2`, `@time`. Access memory list with `GET /v1/users/{user_id}/memories`; disable memory using consent `{"enabled":false}` (deletes stored facts). The browser consent checkbox is not a persisted status indicator; use the consent endpoint when in doubt.

## Offline reproducible evaluation

```bash
pytest -q
python -m social_agent.evaluation --mode all --cases 10 --filler 12
python scripts/load_test.py --url http://127.0.0.1:8000 --requests 50 --concurrency 5
```

The synthetic preference-recall evaluation compares `off`, `window`, `dual` with **identical** scenarios. `window` and `off` do not use long-term facts. It reports recall accuracy and approximate request latency measured locally for the **deterministic rule model**; these numbers should **never** be presented as production or LLM benchmark gains.

The load test measures HTTP request latency, not streaming TTFT. `ChatMetrics.approx_*_tokens` uses a character-based heuristic, *not* tokenizer counts or provider-billed tokens. SSE uses actual streamed LLM deltas when configured for a streaming-capable OpenAI-compatible backend; mock SSE splits fixed text into chunks.

## Security and privacy boundaries

- Persistent facts require explicit opt-in; opt-out deletes all saved facts. Recent messages are stored for conversation even without long-term consent. `DELETE /v1/users/{user_id}` removes both messages and memories.
- All storage queries are parameterized and scoped by user ID. The UI uses `textContent`, not untrusted HTML insertion.
- **Not safe for a publicly exposed, multi-user deployment.** The user ID is caller-supplied and not authenticated: any holder of the shared API key can read/delete another demo user's records. Restrict to localhost and synthetic data. A production version needs user-bound identity/authz, TLS, secure secret management, encryption, retention policy, deletion verification, rate limits, abuse/safety enforcement, audit logging and privacy review.
- Tool calls use explicit commands, schema/AST restrictions, timeout and numeric limits. They are not a secure sandbox and do not implement autonomous tools or prompt-injection resistance against hostile LLM content.
- SQLite is local single-host storage, not a high-QPS distributed database. No high-concurrency throughput or cost advantage is claimed.

## Project layout

```text
social_agent/
  api.py          # FastAPI REST, stream, consent and deletion
  config.py       # environment settings
  engine.py       # readable agent execution pipeline + metrics
  memory.py       # bounded preference extraction + lexical retrieval
  models.py       # deterministic mock and OpenAI-compatible adapter
  routing.py      # simple/complex heuristic route
  schemas.py      # validated payloads
  storage.py      # SQLite persistence + per-user isolation
  tools.py        # safe arithmetic + UTC time
  evaluation.py   # offline ablation test
scripts/load_test.py
web/index.html
tests/
.github/workflows/ci.yml
```

## Planned experiments (not yet implemented)

1. **Memory quality:** embedding-based retrieval (Qdrant) vs keyword baseline, recency/contradiction handling, incremental summary, privacy-aware extraction. Add datasets with long-range dependencies, paraphrases, distractors and contradictions.
2. **Agent execution:** LangGraph state graph, typed tool-call generation with manual approval, retries, recovery and failure injection.
3. **Evaluation:** manually annotated human gold labels, LLM-as-a-Judge with calibration, per-category recall and contradiction rates. Separate model quality from orchestration outcomes.
4. **Efficiency:** exact cached-prefix eligibility vs semantic response reuse; measure provider-reported tokens, cache hit rate, TTFT, E2E latency and p95/p99 under controlled concurrency and quality constraints.
5. **Deployment:** production authn/authz, observability, migrations, distributed datastore, provider failover and reproducible load testing.

## Resume ethics

Only claim features implemented and demonstrated by code/tests and report **measured outcomes with a reproducible baseline**. Do not present proposed performance numbers (e.g. “45% less cost”) as results. No real-user data or fine-tuning dataset is included.

License: MIT (see LICENSE).

## Publish to a new GitHub repository

Create an empty repository first (do not initialize it with a README), then from inside the extracted project directory:

```bash
git init -b main
git add .
git commit -m "feat: initial Social Agent Engine MVP"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_NEW_REPO.git
git push -u origin main
```

Or point an existing empty GitHub repository at this source directory; do not merge the project into an unrelated existing application's main branch.
