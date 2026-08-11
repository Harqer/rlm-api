from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.db import check_and_reserve_quota, lookup_api_key


async def require_api_key(authorization: str = Header(...)) -> dict:
    """Expects `Authorization: Bearer sk-harqer-...`. Looks up the sha256 hash
    against Supabase — raw keys are never stored, matching the zero-trust
    secrets pattern used across the rest of Quix's stack."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Use: Bearer sk-harqer-...",
        )
    raw_key = authorization.removeprefix("Bearer ").strip()

    key_row = await lookup_api_key(raw_key)
    if key_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key.")

    ok, reason = await check_and_reserve_quota(key_row, estimated_tokens=0)
    if not ok:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=reason)

    return key_row


async def optional_backend_key(x_backend_api_key: str | None = Header(default=None)) -> str | None:
    """BYOK: the caller's own OpenAI/Anthropic/etc key for the model they chose.
    This is what makes the service work with 'whatever other LLM of their choice' —
    we never need to hold every provider's key ourselves."""
    return x_backend_api_key
