import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from noter.agents.planner import run
from noter.exceptions import PlannerError
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


def _mock_response(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [anthropic.types.TextBlock(type="text", text=json.dumps(data))]
    return msg


@pytest.fixture
def mock_anthropic():
    with patch("noter.agents.planner.anthropic.Anthropic") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def test_simple_topic_generates_one_note(mock_anthropic):
    mock_anthropic.messages.create.return_value = _mock_response(_SIMPLE_PLAN)
    result = run("what is backpropagation")
    assert isinstance(result, PlannerOutput)
    assert result.generate_multiple_notes is False
    assert len(result.notes) == 1


def test_broad_topic_generates_multiple_notes(mock_anthropic):
    mock_anthropic.messages.create.return_value = _mock_response(_BROAD_PLAN)
    result = run("RAG")
    assert result.generate_multiple_notes is True
    assert len(result.notes) > 1


def test_search_queries_generated(mock_anthropic):
    mock_anthropic.messages.create.return_value = _mock_response(_SIMPLE_PLAN)
    result = run("what is backpropagation")
    assert len(result.search_queries) >= 1
    assert all(isinstance(q, str) and q for q in result.search_queries)


def test_invalid_output_raises_exception(mock_anthropic):
    bad = MagicMock()
    bad.content = [anthropic.types.TextBlock(type="text", text="not valid json {{{")]
    mock_anthropic.messages.create.return_value = bad
    with pytest.raises(PlannerError):
        run("any topic")


def test_retry_succeeds_on_first_bad_response(mock_anthropic):
    bad = MagicMock()
    bad.content = [anthropic.types.TextBlock(type="text", text="not valid json {{{")]
    good = _mock_response(_SIMPLE_PLAN)
    mock_anthropic.messages.create.side_effect = [bad, good]
    result = run("what is backpropagation")
    assert isinstance(result, PlannerOutput)
    assert mock_anthropic.messages.create.call_count == 2
