from types import SimpleNamespace
from unittest.mock import patch

import pytest

from noter.exceptions import LLMError
from noter.llm import chat


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_returns_message_content():
    with patch("noter.llm.litellm.completion", return_value=_response("hello")) as comp:
        result = chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)
    assert result == "hello"
    kwargs = comp.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o"
    assert kwargs["max_tokens"] == 10
    assert kwargs["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]


def test_api_base_passed_when_set():
    with (
        patch("noter.llm.LLM_API_BASE", "http://localhost:11434"),
        patch("noter.llm.litellm.completion", return_value=_response("ok")) as comp,
    ):
        chat(system="s", user="u", model="ollama_chat/llama3.1", max_tokens=10)
    assert comp.call_args.kwargs["api_base"] == "http://localhost:11434"


def test_api_base_omitted_when_unset():
    with (
        patch("noter.llm.LLM_API_BASE", None),
        patch("noter.llm.litellm.completion", return_value=_response("ok")) as comp,
    ):
        chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)
    assert "api_base" not in comp.call_args.kwargs


def test_empty_content_raises():
    with patch("noter.llm.litellm.completion", return_value=_response("")):
        with pytest.raises(LLMError):
            chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)


def test_none_content_raises():
    with patch("noter.llm.litellm.completion", return_value=_response(None)):
        with pytest.raises(LLMError):
            chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)


def test_malformed_response_wrapped():
    malformed = SimpleNamespace(choices=[])
    with patch("noter.llm.litellm.completion", return_value=malformed):
        with pytest.raises(LLMError):
            chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)


def test_provider_error_wrapped():
    with patch("noter.llm.litellm.completion", side_effect=RuntimeError("boom")):
        with pytest.raises(LLMError):
            chat(system="s", user="u", model="openai/gpt-4o", max_tokens=10)
