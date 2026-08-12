"""
Rough token estimate for computing "what this would have cost as a normal
prompt-stuffed call" vs what RLM actually spent. This is intentionally a
cheap heuristic (chars/4), not a real tokenizer — exact BPE token counts
differ per model/vendor and we don't want to pull in a specific tokenizer
(e.g. tiktoken) that would silently be wrong for non-OpenAI backends. Treat
`estimated_naive_tokens` as directional, not billed truth; `actual` numbers
in the response come straight from the provider's own usage response.
"""

from __future__ import annotations

_CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / _CHARS_PER_TOKEN))
