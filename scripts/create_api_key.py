"""
Mint a new API key.

Usage:
    python scripts/create_api_key.py --owner "spresso-prod" --tier byok --quota 5000000

Prints the raw key ONCE. Only its sha256 hash is stored in Supabase — if you
lose the raw key, you must revoke it (is_active=false) and mint a new one.
"""

from __future__ import annotations

import argparse
import secrets

from app.db import get_client, hash_key


def mint(owner_label: str, tier: str, quota: int | None) -> str:
    raw_key = "sk-harqer-" + secrets.token_urlsafe(32)
    client = get_client()
    client.table("api_keys").insert(
        {
            "key_hash": hash_key(raw_key),
            "key_prefix": raw_key[:16],
            "owner_label": owner_label,
            "tier": tier,
            "monthly_token_quota": quota,
        }
    ).execute()
    return raw_key


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True, help="Label for who/what this key is for")
    parser.add_argument("--tier", default="byok", choices=["byok", "managed"])
    parser.add_argument("--quota", type=int, default=None, help="Monthly token quota (omit = unlimited)")
    args = parser.parse_args()

    key = mint(args.owner, args.tier, args.quota)
    print("\nNew API key (shown once — store it now):\n")
    print(f"  {key}\n")
