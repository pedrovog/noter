import json
from unittest.mock import patch

import pytest

from noter.agents.planner import run
from noter.exceptions import LLMError, PlannerError
from noter.schemas import PlannerOutput

_SIMPLE_PLAN = {
    "main_title": "Backpropagation",
    "generate_multiple_notes": False,
    "notes": [
        {
            "title": "Backpropagation",
            "subtopics": ["gradient descent", "chain rule", "weight update"],
            "focus": "Explain the algorithm with mathematical detail.",
        }
    ],
    "search_queries": [
        "backpropagation neural network gradient",
        "chain rule calculus deep learning",
        "weight update SGD explained",
    ],
}

_BROAD_PLAN = {
    "main_title": "Retrieval-Augmented Generation",
    "generate_multiple_notes": True,
    "notes": [
        {
            "title": "RAG Architecture",
            "subtopics": ["retrieval", "vector databases", "embedding"],
            "focus": "Focus on the technical architecture.",
        },
        {
            "title": "RAG Evaluation",
            "subtopics": ["metrics", "benchmarks", "faithfulness"],
            "focus": "Focus on evaluation methods.",
        },
        {
            "title": "RAG in Production",
            "subtopics": ["chunking", "indexing", "latency"],
            "focus": "Focus on deployment considerations.",
        },
        {
            "title": "RAG vs Fine-tuning",
            "subtopics": ["trade-offs", "cost", "use cases"],
            "focus": "Compare RAG with fine-tuning.",
        },
    ],
    "search_queries": [
        "retrieval augmented generation architecture",
        "RAG vector store embedding",
        "RAG evaluation faithfulness",
        "RAG vs fine-tuning LLM",
    ],
}


def _mock_response(data: dict) -> str:
    return json.dumps(data)


@pytest.fixture
def mock_chat():
    with patch("noter.agents.planner.chat") as chat:
        yield chat


def test_simple_topic_generates_one_note(mock_chat):
    mock_chat.return_value = _mock_response(_SIMPLE_PLAN)
    result = run("what is backpropagation")
    assert isinstance(result, PlannerOutput)
    assert result.generate_multiple_notes is False
    assert len(result.notes) == 1


def test_broad_topic_generates_multiple_notes(mock_chat):
    mock_chat.return_value = _mock_response(_BROAD_PLAN)
    result = run("RAG")
    assert result.generate_multiple_notes is True
    assert len(result.notes) > 1


def test_search_queries_generated(mock_chat):
    mock_chat.return_value = _mock_response(_SIMPLE_PLAN)
    result = run("what is backpropagation")
    assert len(result.search_queries) >= 1
    assert all(isinstance(q, str) and q for q in result.search_queries)


def test_invalid_output_raises_exception(mock_chat):
    mock_chat.return_value = "not valid json {{{"
    with pytest.raises(PlannerError):
        run("any topic")


def test_retry_succeeds_on_first_bad_response(mock_chat):
    mock_chat.side_effect = ["not valid json {{{", _mock_response(_SIMPLE_PLAN)]
    result = run("what is backpropagation")
    assert isinstance(result, PlannerOutput)
    assert mock_chat.call_count == 2


def test_llm_error_propagates(mock_chat):
    # A provider/transport failure surfaces as LLMError — not masked as a
    # PlannerError "invalid output" — and is not retried.
    mock_chat.side_effect = LLMError("network failure")
    with pytest.raises(LLMError):
        run("any topic")
    assert mock_chat.call_count == 1
