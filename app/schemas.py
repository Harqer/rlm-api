from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Backend = Literal[
    "openai", "portkey", "openrouter", "vercel", "vllm", "anthropic", "azure_openai", "gemini"
]


class ContextVariable(BaseModel):
    """One named block that gets loaded into the RLM's REPL as a real Python
    variable, rather than concatenated into the prompt string. This is the
    literal mechanism the RLM paper uses to fight context rot: instead of
    stuffing a 500-page doc or a folder of skill files into the attention
    window, the model gets a variable it can .find() / .slice() / query
    over on demand.

    `name` becomes the REPL variable name (e.g. context["no_mock_skill"]),
    so keep it a valid Python identifier.
    """

    name: str = Field(..., description="REPL variable name, e.g. 'no_mock_skill' or 'codebase_dump'")
    content: str = Field(..., description="The raw text for this variable — a skill file, doc, transcript, code dump, etc.")


class CompletionRequest(BaseModel):
    # The small, load-bearing instruction the root model actually sees up front —
    # analogous to RLM's `root_prompt`.
    prompt: str = Field(..., description="The instruction/question. Kept small and in-context.")

    # The large payload(s) offloaded into REPL variables instead of the prompt.
    context: list[ContextVariable] = Field(
        default_factory=list,
        description="Large content (skills, docs, code, transcripts) turned into REPL variables.",
    )

    backend: Backend = Field(default="anthropic")
    model: str = Field(default="claude-sonnet-4-5")
    max_iterations: int = Field(default=12, ge=1, le=30)
    max_depth: int = Field(default=1, ge=0, le=1, description="1 = allow recursive sub-calls; 0 = REPL-only, no sub-LLM spawning")
    max_budget_usd: float | None = Field(default=None, description="Hard cost ceiling for this single call")
    verbose: bool = Field(default=False)
    backend_kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Extra kwargs forwarded to the backend client, e.g. {'base_url': ...}"
    )


class UsageSummaryOut(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


class CompletionResponse(BaseModel):
    response: str
    root_model: str
    execution_time_s: float
    usage: UsageSummaryOut
    trajectory: dict[str, Any] | None = None
