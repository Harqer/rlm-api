# Harqer RLM API

A **token-cost harness**: one API-key-protected endpoint that auto-routes
every call between a cheap direct passthrough and MIT CSAIL's real
**Recursive Language Models** (`rlms` on PyPI — Zhang, Kraska, Khattab,
arXiv:2512.24601), whichever is actually cheaper for that request's context
size — and reports the real token savings, not a claimed one. Fully model-
agnostic: `backend`/`model` are just request parameters, so the harness
sits in front of Anthropic, OpenAI, Gemini, OpenRouter, Portkey, vLLM,
Azure OpenAI, or Vercel AI Gateway identically.

This wraps the real `rlm.RLM` class and the real `rlm.clients` factory
directly. It does not reimplement RLM's REPL/recursion logic or any
provider's SDK.

## Why this exists

Every app that stuffs a big system prompt / doc / skill file into every
call pays full token price for it, every single time, on whichever model
it's using. This harness gives you one call shape that:

1. **`mode="direct"`** — plain passthrough, all context concatenated into
   the prompt. Cheapest for small context, zero RLM overhead.
2. **`mode="rlm"`** — offloads context into REPL variables the model
   queries on demand instead of reading in full. Wins once context is large
   enough that the REPL overhead is smaller than what you'd otherwise
   re-pay for on every internal step.
3. **`mode="auto"`** (default) — picks between the two per request based on
   total context size (`AUTO_MODE_CONTEXT_CHAR_THRESHOLD`, default ~24k
   chars / ~6k tokens). You call the same endpoint regardless of payload
   size; the harness minimizes cost for you.

Every response includes a `savings` block comparing the naive "concatenate
everything into one prompt" token estimate against the real tokens the
provider actually billed.

## Quickstart

```bash
cp .env.example .env   # fill in SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
pip install -r requirements.txt

# One-time: apply scripts/supabase_schema.sql in the Supabase SQL editor

# Mint yourself a key
python scripts/create_api_key.py --owner "local-dev" --tier byok

uvicorn app.main:app --reload
```

## Calling it

```bash
curl -X POST http://localhost:8080/v1/completions \
  -H "Authorization: Bearer sk-harqer-..." \
  -H "X-Backend-Api-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What does the no-mock skill forbid? Cite the exact rules.",
    "context": [
      {"name": "no_mock_skill", "content": "Rule 1: never swallow exceptions..."},
      {"name": "codebase_dump", "content": "<paste a huge file / transcript / skill folder here>"}
    ],
    "mode": "auto",
    "backend": "anthropic",
    "model": "claude-sonnet-4-5",
    "max_iterations": 12,
    "max_depth": 1
  }'
```

Response:

```json
{
  "response": "...",
  "root_model": "claude-sonnet-4-5",
  "execution_time_s": 4.2,
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 340,
    "total_tokens": 1540,
    "cost_usd": 0.0093
  },
  "savings": {
    "mode_used": "rlm",
    "estimated_naive_tokens": 9800,
    "actual_total_tokens": 1540,
    "tokens_saved": 8260,
    "pct_saved": 84.29
  }
}
```

`estimated_naive_tokens` is a chars/4 heuristic for what a plain
prompt-stuffed call to the same model would have cost — deliberately
approximate (see `app/token_estimate.py`) rather than pulling in a
provider-specific tokenizer that would be wrong for the other 7 backends.
`actual_total_tokens` and `cost_usd` come straight from the provider's own
usage response — real numbers, not estimates.

Each entry in `context` becomes a real Python variable inside the RLM's REPL
when `mode="rlm"` runs — the root model decides what to `.find()`, slice,
regex, or hand off to a cheap sub-LLM call, rather than everything being
crammed into the attention window up front. That's the literal mechanism,
not a metaphor — verified against `rlm.core.types.QueryMetadata` directly
(see `tests/`).

## Integrating with "whatever other LLM" (fully agnostic)

`backend` accepts: `openai`, `anthropic`, `gemini`, `openrouter`, `portkey`,
`vllm`, `azure_openai`, `vercel`. Set `model` to that backend's model name
and pass the matching key via `X-Backend-Api-Key`. No code changes needed
per backend — it's a request parameter, same as RLM's own `RLM(backend=...)`.

## Sandbox choice is a *separate* dial from LLM choice

`environment` picks where the model-written code actually runs — independent
of which LLM answered. Any backend can run in either environment:

- `"local"` (default) — runs in-process. Zero isolation, fastest, fine for
  your own trusted server-to-server calls.
- `"e2b"` — runs in a Firecracker microVM via E2B. Real kernel boundary; use
  this once you're accepting calls from third parties or untrusted context.
  Requires `E2B_API_KEY` set on the deployment (operator infra cost — the
  caller's BYOK key only covers the LLM, not the sandbox).

```json
{
  "prompt": "...",
  "context": [...],
  "backend": "openai",
  "model": "gpt-5-mini",
  "environment": "e2b"
}
```

If `environment="e2b"` is requested but `E2B_API_KEY` isn't configured, the
API returns a clean `400` explaining exactly that — it won't silently fall
back to unsandboxed execution.

Other `rlms`-native environments (`docker`, `modal`, `daytona`, `prime`) can
be added the same way: extend `ALLOWED_ENVIRONMENT_KINDS` in `app/config.py`
and add a branch in `_resolve_environment()` in `app/rlm_service.py`. A GCP
Cloud Run sandboxes adapter (gVisor, runs inside this same Cloud Run service
— no second thing to deploy) is a good next one to write; it isn't one of
`rlms`' built-in environment types, so it needs a small custom `IsolatedEnv`
subclass rather than a one-line config change.

## Deploying

```bash
PROJECT_ID=your-gcp-project REGION=us-west1 SUPABASE_URL=https://xxx.supabase.co \
  ./deploy/cloudrun.sh
```

Secrets come from GCP Secret Manager (`--set-secrets`), matching the
zero-trust pattern already used on the Spresso/QBitcoin backend — nothing
sensitive is baked into the image or checked into git.

## Security note before multi-tenant production use

`RLM_ENVIRONMENT_KIND=local` (default) runs the REPL in the same process as
the API server — fine for a single trusted caller, not safe for arbitrary
untrusted multi-tenant traffic, since a malicious prompt could in principle
get the root model to write code that touches the host process. `rlms`
ships isolated alternatives (`docker`, `modal`, `prime`, `daytona`, `e2b`) —
switch to one of those (`environment_kwargs` in `app/rlm_service.py`) before
opening this up beyond your own apps.

## Verified against the real library

- Installed `rlms==0.1.3` from PyPI (not vendored/reimplemented).
- Confirmed `RLM.__init__` / `RLM.completion` signatures directly via
  `inspect.signature` rather than assumed.
- Confirmed the context-variable dict shape against `rlm.core.types.QueryMetadata`.
- Ran a live call through the full stack (schema → REPL-variable conversion
  → real `RLM` → real `anthropic` client) — reached Anthropic's servers and
  got a real (billing) error back, proving the wiring, not a stub.
- `tests/test_live_integration.py` is ready to rerun end-to-end with a
  funded key — no mocks anywhere in this repo.
