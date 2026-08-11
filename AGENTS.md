# AGENTS.md

Agent-agnostic entry point for this repo (Harqer RLM API). Any coding agent
working here should read this first, then `CLAUDE.md` for always-on rules.

## What this is

A SaaS API-key layer in front of MIT CSAIL's real `rlms` package (Recursive
Language Models, Zhang/Kraska/Khattab, arXiv:2512.24601). It exposes one
endpoint — `POST /v1/completions` — that turns large context (skills, docs,
code dumps, transcripts) into REPL variables an LLM can programmatically
inspect, instead of stuffing everything into the prompt. This is the fix for
context rot the RLM paper demonstrates.

## Layout

- `app/main.py` — FastAPI routes
- `app/rlm_service.py` — the actual wrapper around `rlm.RLM` (real library, not reimplemented)
- `app/auth.py`, `app/db.py` — API key auth + usage ledger, Supabase-backed
- `app/schemas.py` — request/response contracts, including `ContextVariable` (the "context → variable" mechanism)
- `scripts/supabase_schema.sql` — run once against your Supabase project
- `scripts/create_api_key.py` — mint new keys
- `deploy/cloudrun.sh` — Cloud Run deploy, secrets via GCP Secret Manager

## Ground rules

See `CLAUDE.md`. In short: no mocks, no swallowed exceptions, real
integration tests only. This project was built and verified against the
live `rlms` PyPI package and a real Anthropic API call (see
`tests/test_live_integration.py`).
