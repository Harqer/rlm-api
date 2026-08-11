"""
Supabase (Postgres) access layer.

Two tables (see scripts/supabase_schema.sql):

  api_keys(id, key_hash, owner_label, tier, monthly_token_quota,
           tokens_used_this_period, is_active, created_at)

  usage_events(id, api_key_id, backend, model, prompt_tokens,
               completion_tokens, cost_usd, execution_time_s,
               status, created_at)

We use the service-role key server-side only (never shipped to clients),
so RLS is bypassed here by design — this process is the trusted backend.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from app.config import settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def hash_key(raw_key: str) -> str:
    """We never store raw API keys — only their sha256 hash, same pattern as GitHub/Stripe keys."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def lookup_api_key(raw_key: str) -> dict[str, Any] | None:
    key_hash = hash_key(raw_key)
    resp = (
        get_client()
        .table("api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


async def check_and_reserve_quota(key_row: dict[str, Any], estimated_tokens: int) -> tuple[bool, str | None]:
    """Soft quota check before spawning an RLM run. Actual usage is reconciled after
    the call completes via record_usage(), since RLM token spend can't be known upfront."""
    quota = key_row.get("monthly_token_quota")
    used = key_row.get("tokens_used_this_period", 0)
    if quota is not None and used >= quota:
        return False, f"Monthly token quota exhausted ({used}/{quota})."
    return True, None


async def record_usage(
    api_key_id: str,
    backend: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    execution_time_s: float,
    status: str,
) -> None:
    client = get_client()
    client.table("usage_events").insert(
        {
            "api_key_id": api_key_id,
            "backend": backend,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "execution_time_s": execution_time_s,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()

    total_tokens = prompt_tokens + completion_tokens
    client.rpc(
        "increment_tokens_used",
        {"key_id": api_key_id, "delta": total_tokens},
    ).execute()
