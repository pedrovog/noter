import os

# LLM provider (optional). When set and a model has no "<provider>/" prefix,
# it is joined as "<provider>/<model>". Model strings may also carry the prefix
# directly (e.g. "openai/gpt-4o", "ollama_chat/llama3.1"), in which case this
# is ignored. Empty/unset → rely on the model string alone.
LLM_PROVIDER = os.environ.get("NOTER_PROVIDER")

# Base URL for the LLM endpoint. Required for self-hosted/local servers such as
# Ollama (e.g. "http://localhost:11434"). Passed to litellm.completion as
# api_base only when set.
LLM_API_BASE = os.environ.get("NOTER_API_BASE")


def _resolve(model: str) -> str:
    """Return a fully-qualified LiteLLM model string.

    If the model already carries a "<provider>/" prefix, use it as-is.
    Otherwise prefix it with NOTER_PROVIDER when that is set.
    """
    if "/" in model or not LLM_PROVIDER:
        return model
    return f"{LLM_PROVIDER}/{model}"


DEFAULT_MODEL = _resolve(os.environ.get("NOTER_MODEL", "anthropic/claude-sonnet-4-6"))

INBOX_SUBFOLDER = os.environ.get("NOTER_INBOX", "noter")

# Per-agent overrides — fall back to DEFAULT_MODEL if not set
PLANNER_MODEL = _resolve(os.environ.get("NOTER_PLANNER_MODEL", DEFAULT_MODEL))
SYNTHESIZER_MODEL = _resolve(os.environ.get("NOTER_SYNTHESIZER_MODEL", DEFAULT_MODEL))
WRITER_MODEL = _resolve(os.environ.get("NOTER_WRITER_MODEL", DEFAULT_MODEL))
LINKER_MODEL = _resolve(os.environ.get("NOTER_LINKER_MODEL", DEFAULT_MODEL))
