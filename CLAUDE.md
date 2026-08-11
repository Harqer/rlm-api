# CLAUDE.md — always-on rules for this repo

These apply to every session, unconditionally (skills are conditional;
this file is not).

## Completion gates

- No swallowed exceptions. `except Exception: pass` is never acceptable —
  errors surface to the API caller as real HTTP error responses (see
  `app/main.py`'s exception handling in `/v1/completions`).
- No auth weakening in tests. Live integration tests hit the real Supabase
  project and real LLM backend, using the same `require_api_key` path
  production traffic uses. No test-only auth bypass.
- No timeout masking. `RLM_REQUEST_TIMEOUT_S` is enforced by `rlm.RLM`
  itself (`max_timeout`); don't catch and retry-forever around it.
- No mocks for integration tests. `tests/test_live_integration.py` makes a
  real HTTP call to a running instance of this API, which makes a real call
  to `rlm.RLM`, which makes a real call to the configured LLM backend.

## Secrets

- Never commit `.env`. `SUPABASE_SERVICE_ROLE_KEY` and any
  `MANAGED_*_API_KEY` come from GCP Secret Manager in prod
  (`deploy/cloudrun.sh`), local `.env` in dev (gitignored).
- Raw API keys for this service are never stored — only sha256 hashes
  (`app/db.py:hash_key`). BYOK backend keys arrive per-request via the
  `X-Backend-Api-Key` header and are never persisted.

## REPL environment

- `RLM_ENVIRONMENT_KIND=local` (default) runs the REPL in-process — fine for
  a single trusted tenant or dev. Before onboarding untrusted multi-tenant
  traffic, switch to `docker`/`modal`/`e2b` (see README security note) so
  one tenant's context can't execute code against another's process.
