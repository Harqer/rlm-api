from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.auth import optional_backend_key, require_api_key
from app.db import record_usage
from app.rlm_service import BackendCredentialError, EnvironmentNotAllowedError, run_completion
from app.schemas import CompletionRequest, CompletionResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("harqer-rlm-api")

app = FastAPI(
    title="Harqer RLM API",
    version="0.1.0",
    description=(
        "SaaS wrapper around MIT CSAIL's Recursive Language Models (rlms). "
        "Turns large context/skills into REPL variables to fight context rot. "
        "BYOK: bring the API key for whichever LLM backend you choose."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your actual frontend origins before prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/completions", response_model=CompletionResponse)
async def completions(
    req: CompletionRequest,
    key_row: dict = Depends(require_api_key),
    backend_key: str | None = Depends(optional_backend_key),
):
    try:
        result = await run_completion(req, byok_backend_key=backend_key)
    except BackendCredentialError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EnvironmentNotAllowedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001 — surface real errors to the caller, don't swallow
        logger.exception("RLM completion failed")
        await record_usage(
            api_key_id=key_row["id"],
            backend=req.backend,
            model=req.model,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            execution_time_s=0.0,
            status="error",
        )
        raise HTTPException(status_code=502, detail=f"RLM backend error: {e}")

    usage = result["usage"]
    await record_usage(
        api_key_id=key_row["id"],
        backend=req.backend,
        model=req.model,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        cost_usd=usage["cost_usd"],
        execution_time_s=result["execution_time_s"],
        status="ok",
    )

    return CompletionResponse(
        response=result["response"],
        root_model=result["root_model"],
        execution_time_s=result["execution_time_s"],
        usage=usage,
        savings=result["savings"],
    )
