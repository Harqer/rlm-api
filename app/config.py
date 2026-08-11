"""
Config — all settings sourced from environment variables.

Local dev: populate a `.env` file (see .env.example) and this loads via
python-dotenv. In Cloud Run, these are injected as env vars, with secrets
(SUPABASE_SERVICE_ROLE_KEY, backend LLM keys for the managed tier) coming
from GCP Secret Manager via the Cloud Run --set-secrets flag — no secret
material is ever baked into the image or checked into git.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing required env var {name}. Copy .env.example to .env and fill it in "
            f"(or set it in Cloud Run via --set-secrets/--set-env-vars)."
        )
    return val


class Settings:
    # Supabase (Postgres) — API key registry + usage ledger
    SUPABASE_URL: str = _require("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY: str = _require("SUPABASE_SERVICE_ROLE_KEY")

    # Managed-tier backend keys (optional). If unset, callers must bring their
    # own LLM API key via the X-Backend-Api-Key header (BYOK — recommended).
    MANAGED_ANTHROPIC_API_KEY: str | None = os.environ.get("MANAGED_ANTHROPIC_API_KEY")
    MANAGED_OPENAI_API_KEY: str | None = os.environ.get("MANAGED_OPENAI_API_KEY")

    # RLM execution defaults — overridable per-request within safe caps
    DEFAULT_BACKEND: str = os.environ.get("RLM_DEFAULT_BACKEND", "anthropic")
    DEFAULT_MODEL: str = os.environ.get("RLM_DEFAULT_MODEL", "claude-sonnet-4-5")
    MAX_ITERATIONS_CAP: int = int(os.environ.get("RLM_MAX_ITERATIONS_CAP", "30"))
    MAX_DEPTH_CAP: int = int(os.environ.get("RLM_MAX_DEPTH_CAP", "1"))
    REQUEST_TIMEOUT_S: float = float(os.environ.get("RLM_REQUEST_TIMEOUT_S", "180"))

    # REPL environment — 'local' for dev, use 'docker'/'modal'/'e2b' in prod
    # once this handles untrusted multi-tenant context. See README security note.
    ENVIRONMENT_KIND: str = os.environ.get("RLM_ENVIRONMENT_KIND", "local")

    PORT: int = int(os.environ.get("PORT", "8080"))


settings = Settings()
