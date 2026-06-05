"""Unified LLM access via LiteLLM.

This is the only module that imports ``litellm``. Every agent calls
:func:`chat` with a system prompt, a user message, a fully-resolved model
string (e.g. ``anthropic/claude-sonnet-4-6``, ``openai/gpt-4o``,
``ollama_chat/llama3.1``) and a token budget, and receives back a plain string.

Provider selection is driven entirely by the model prefix, so swapping
providers — including self-hosted servers like Ollama — requires no code
changes, only ``NOTER_MODEL`` / ``NOTER_PROVIDER`` / ``NOTER_API_BASE`` env vars.
"""

from typing import Any

import litellm

from noter.config import LLM_API_BASE
from noter.exceptions import LLMError


def chat(*, system: str, user: str, model: str, max_tokens: int) -> str:
    """Send a single-turn system+user prompt and return the text response.

    Raises:
        LLMError: if the provider call fails or returns empty content.
    """
    # Idempotent global config — kept here so importing this module has no
    # side effects. suppress_debug_info silences LiteLLM's provider hints and
    # cost tables; drop_params silently drops params a provider rejects (helps
    # local models that don't accept every OpenAI field).
    litellm.suppress_debug_info = True
    litellm.drop_params = True

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # noter wants structured JSON, not chain-of-thought. "none" disables
        # thinking on reasoning models (Gemini 2.5, Claude) so reasoning tokens
        # don't eat the max_tokens budget and truncate the JSON. drop_params
        # discards it for providers/models that don't support reasoning_effort.
        "reasoning_effort": "none",
    }
    if LLM_API_BASE:
        kwargs["api_base"] = LLM_API_BASE

    try:
        response = litellm.completion(**kwargs)
        content: str | None = response.choices[0].message.content
    except Exception as exc:
        raise LLMError(f"LLM call failed for model {model!r}: {exc}") from exc

    if not content:
        raise LLMError(f"LLM returned empty content for model {model!r}")
    return content
