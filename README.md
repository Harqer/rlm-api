# Harqer RLM API

A SaaS API-key layer over MIT CSAIL's real **Recursive Language Models**
(`rlms` on PyPI — Zhang, Kraska, Khattab, arXiv:2512.24601). One endpoint,
BYOK for any LLM backend, context turned into REPL variables instead of
prompt-stuffed text — the actual fix for context rot the paper demonstrates,
not a paraphrase of it.

This wraps the real `rlm.RLM` class directly. It does not reimplement RLM's
REPL/recursion logic.

## Why this exists

`rlms` is a Python library you `pip install` and call in-process. This repo
turns it into a hosted API so any app — regardless of language — can POST a
prompt + large context and get back an answer, without shipping Python or
managing REPL sandboxes itself. You bring the API key for whichever LLM you
want (Anthropic, OpenAI, Gemini, OpenRouter, Portkey, vLLM, Azure OpenAI).

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
  }
}
```

Each entry in `context` becomes a real Python variable inside the RLM's REPL
— the root model decides what to `.find()`, slice, regex, or hand off to a
cheap sub-LLM call, rather than everything being crammed into the attention
window up front. That's the literal mechanism, not a metaphor — verified
against `rlm.core.types.QueryMetadata` directly (see `tests/`).

## Integrating with "whatever other LLM"

`backend` accepts: `openai`, `anthropic`, `gemini`, `openrouter`, `portkey`,
`vllm`, `azure_openai`, `vercel`. Set `model` to that backend's model name
and pass the matching key via `X-Backend-Api-Key`. No code changes needed
per backend — it's a request parameter, same as RLM's own `RLM(backend=...)`.

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
