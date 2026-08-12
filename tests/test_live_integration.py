"""
Real, no-mock integration test. Starts nothing fake: run this against a live
instance of the API (local uvicorn or deployed Cloud Run URL), with a real
Supabase project and a real, funded LLM backend key.

Setup:
    1. Apply scripts/supabase_schema.sql to your Supabase project.
    2. python scripts/create_api_key.py --owner "test" --tier byok
    3. uvicorn app.main:app --reload   (in another terminal)
    4. export HARQER_API_KEY=<key from step 2>
    5. export ANTHROPIC_API_KEY=<your real, funded Anthropic key>
    6. python tests/test_live_integration.py
"""

from __future__ import annotations

import os
import sys

import httpx

API_BASE = os.environ.get("HARQER_API_BASE", "http://localhost:8080")


def main() -> None:
    harqer_key = os.environ.get("HARQER_API_KEY")
    backend_key = os.environ.get("ANTHROPIC_API_KEY")
    if not harqer_key or not backend_key:
        print("Set HARQER_API_KEY and ANTHROPIC_API_KEY env vars first. See docstring.")
        sys.exit(1)

    payload = {
        "prompt": (
            "How many times does the word ERROR appear in the log variable, "
            "and on which line numbers (1-indexed)? Answer concisely."
        ),
        "context": [
            {
                "name": "log",
                "content": "\n".join(
                    [
                        "INFO boot sequence start",
                        "INFO loading config",
                        "ERROR failed to connect to db, retrying",
                        "INFO retry ok",
                        "WARN cache miss",
                        "ERROR timeout on upstream call",
                        "INFO request served",
                        "ERROR disk usage above 90 percent",
                        "INFO shutdown clean",
                    ]
                ),
            }
        ],
        "mode": "auto",
        "backend": "anthropic",
        "model": "claude-sonnet-4-5",
        "max_iterations": 8,
        "max_depth": 1,
    }

    resp = httpx.post(
        f"{API_BASE}/v1/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {harqer_key}",
            "X-Backend-Api-Key": backend_key,
        },
        timeout=200,
    )
    resp.raise_for_status()
    data = resp.json()

    print("=== RESPONSE ===")
    print(data["response"])
    print("=== USAGE ===")
    print(data["usage"])
    print("=== SAVINGS (harness routing decision) ===")
    print(data["savings"])

    assert "3" in data["response"] or "three" in data["response"].lower(), (
        "Expected the model to find 3 ERROR lines — check response above."
    )
    print("\nPASS")


if __name__ == "__main__":
    main()
