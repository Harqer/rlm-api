"""
Thin, honest wrapper around the real `rlms` PyPI package (MIT CSAIL,
Zhang/Kraska/Khattab — arXiv:2512.24601). We do not reimplement RLM's
REPL/recursion logic; we import and drive `rlm.RLM` directly and add:

  1. API-key-scoped backend credential resolution (BYOK or managed)
  2. Multiple named context blocks -> REPL variables (dict prompt form)
  3. Per-tenant safety caps (iterations, depth, budget, timeout)
  4. Usage/cost extraction into a JSON-friendly shape for the API response
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from rlm import RLM

from app.config import settings
from app.schemas import CompletionRequest

# E2B's Sandbox.create() (called inside rlm's E2BREPL) reads E2B_API_KEY
# straight from the process environment — there's no api_key kwarg to pass
# per-call. So we set it once, at import time, from our own config layer
# (which itself came from GCP Secret Manager in prod). This is operator
# infra, not a per-caller BYOK credential.
if settings.E2B_API_KEY:
    os.environ.setdefault("E2B_API_KEY", settings.E2B_API_KEY)


class BackendCredentialError(Exception):
    pass


class EnvironmentNotAllowedError(Exception):
    pass


def _resolve_backend_api_key(backend: str, byok_key: str | None) -> str:
    """BYOK takes priority. Falls back to a managed key only if the operator
    configured one for that backend (opt-in, off by default)."""
    if byok_key:
        return byok_key

    managed = {
        "anthropic": settings.MANAGED_ANTHROPIC_API_KEY,
        "openai": settings.MANAGED_OPENAI_API_KEY,
    }.get(backend)

    if managed:
        return managed

    raise BackendCredentialError(
        f"No API key available for backend '{backend}'. Pass one via the "
        f"X-Backend-Api-Key header (BYOK), or ask the operator to configure "
        f"a managed key for this backend."
    )


def _build_repl_prompt(req: CompletionRequest) -> str | dict[str, Any]:
    """This is the literal 'turn context into variables' mechanism.

    If there's no context, we just pass the prompt straight through as a
    plain string (RLM still spawns a REPL, just with nothing extra loaded).

    If there IS context, we pass a dict: each entry becomes a REPL variable
    the root model can inspect programmatically (.find(), slicing, regex,
    or handing a slice to a cheap sub-LLM) instead of it being crammed into
    the attention window up front. This is what actually fixes context rot —
    the model decides what to read, instead of everything being force-fed.
    """
    if not req.context:
        return req.prompt

    variables = {block.name: block.content for block in req.context}
    # RLM's dict-prompt form expects the instruction plus the variable payloads;
    # QueryMetadata (inside rlm.core) introspects this dict to describe available
    # variables to the root model in the system prompt automatically.
    variables["instruction"] = req.prompt
    return variables


def _backend_kwargs(req: CompletionRequest, api_key: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model_name": req.model, "api_key": api_key}
    kwargs.update(req.backend_kwargs)
    return kwargs


def _resolve_environment(req: CompletionRequest) -> tuple[str, dict[str, Any]]:
    """Sandbox choice is independent of LLM choice — any backend can run in
    any environment. Operator controls which environments are enabled at all
    (ALLOWED_ENVIRONMENT_KINDS) since e2b carries real infra cost per call."""
    kind = req.environment
    if kind not in settings.ALLOWED_ENVIRONMENT_KINDS:
        raise EnvironmentNotAllowedError(
            f"Environment '{kind}' is not enabled on this deployment. "
            f"Allowed: {sorted(settings.ALLOWED_ENVIRONMENT_KINDS)}."
        )
    if kind == "e2b":
        if not settings.E2B_API_KEY:
            raise EnvironmentNotAllowedError(
                "environment='e2b' was requested but this deployment has no E2B_API_KEY configured. "
                "Set E2B_API_KEY (operator infra, not BYOK) or use environment='local'."
            )
        return "e2b", {"timeout": settings.E2B_SANDBOX_TIMEOUT_S}
    return "local", {}


async def run_completion(req: CompletionRequest, byok_backend_key: str | None) -> dict[str, Any]:
    api_key = _resolve_backend_api_key(req.backend, byok_backend_key)
    environment, environment_kwargs = _resolve_environment(req)

    max_iterations = min(req.max_iterations, settings.MAX_ITERATIONS_CAP)
    max_depth = min(req.max_depth, settings.MAX_DEPTH_CAP)

    rlm = RLM(
        backend=req.backend,
        backend_kwargs=_backend_kwargs(req, api_key),
        environment=environment,
        environment_kwargs=environment_kwargs,
        max_iterations=max_iterations,
        max_depth=max_depth,
        max_budget=req.max_budget_usd,
        max_timeout=settings.REQUEST_TIMEOUT_S,
        verbose=req.verbose,
    )

    prompt = _build_repl_prompt(req)

    start = time.perf_counter()
    # rlm.RLM.completion() is synchronous (it drives a REPL + blocking LM calls),
    # so we run it in a worker thread to avoid blocking the FastAPI event loop.
    completion = await asyncio.to_thread(rlm.completion, prompt, req.prompt)
    elapsed = time.perf_counter() - start

    usage = completion.usage_summary
    input_tokens = usage.total_input_tokens
    output_tokens = usage.total_output_tokens
    cost = usage.total_cost or 0.0

    return {
        "response": completion.response,
        "root_model": completion.root_model,
        "execution_time_s": completion.execution_time or elapsed,
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost, 6),
        },
        "raw_usage_summary": usage.to_dict(),
    }
