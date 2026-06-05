import json
import logging
from unittest.mock import patch

import pytest

from noter.agents.synthesizer import _WORD_LIMIT, _truncate, run
from noter.exceptions import SynthesizerError
from noter.schemas import PlannerOutput, SourceResult, SynthesizedNote

_NOTE_SPEC_ARCH = {
    "title": "RAG Architecture",
    "subtopics": ["retrieval", "vector databases"],
    "focus": "Focus on vector database architecture.",
}

_NOTE_SPEC_EVAL = {
    "title": "RAG Evaluation",
    "subtopics": ["metrics"],
    "focus": "Focus on evaluation metrics.",
}

_SYNTH_NOTE = {
    "note_title": "RAG Architecture",
    "core_concept": "RAG combines retrieval with generation.",
    "subtopics": [{"title": "Retrieval", "content": "Vectors are queried from an index."}],
    "sources_used": [{"url": "https://example.com", "title": "RAG Paper"}],
}

_SIMPLE_PLAN = PlannerOutput(
    main_title="RAG",
    generate_multiple_notes=False,
    notes=[_NOTE_SPEC_ARCH],
    search_queries=["RAG architecture"],
)

_BROAD_PLAN = PlannerOutput(
    main_title="RAG",
    generate_multiple_notes=True,
    notes=[_NOTE_SPEC_ARCH, _NOTE_SPEC_EVAL],
    search_queries=["RAG architecture", "RAG evaluation"],
)


def _make_source(url="https://a.com", title="A", content="word " * 100, source="auto"):
    return SourceResult(url=url, title=title, content=content, source=source)


def _mock_response(data):
    return json.dumps(data)


@pytest.fixture
def mock_chat():
    with patch("noter.agents.synthesizer.chat") as chat:
        yield chat


def test_user_sources_prioritized_in_context(mock_chat):
    mock_chat.return_value = _mock_response(_SYNTH_NOTE)
    user_src = _make_source(url="https://user.com", title="User Source", source="user")
    auto_sources = [_make_source(url=f"https://auto{i}.com", title=f"Auto {i}") for i in range(5)]
    run(_SIMPLE_PLAN, [*auto_sources, user_src])
    user_msg = mock_chat.call_args.kwargs["user"]
    assert user_msg.index("https://user.com") < user_msg.index("https://auto0.com")


def test_truncation_respects_token_limit():
    result = _truncate("word " * 10_000)
    assert len(result.split()) == _WORD_LIMIT


def test_multiple_notes_generated_for_broad_topic(mock_chat):
    mock_chat.return_value = _mock_response(_SYNTH_NOTE)
    results = run(_BROAD_PLAN, [_make_source()])
    assert len(results) == 2
    assert mock_chat.call_count == 2
    assert all(isinstance(r, SynthesizedNote) for r in results)


def test_one_note_output_for_simple_topic(mock_chat):
    mock_chat.return_value = _mock_response(_SYNTH_NOTE)
    results = run(_SIMPLE_PLAN, [_make_source()])
    assert len(results) == 1
    assert isinstance(results[0], SynthesizedNote)


def test_invalid_json_raises_synthesizer_error(mock_chat):
    mock_chat.return_value = "not valid json {{{"
    with pytest.raises(SynthesizerError):
        run(_SIMPLE_PLAN, [_make_source()])
    assert mock_chat.call_count == 2


def test_retry_succeeds_on_second_attempt(mock_chat):
    mock_chat.side_effect = ["not valid json {{{", _mock_response(_SYNTH_NOTE)]
    results = run(_SIMPLE_PLAN, [_make_source()])
    assert len(results) == 1
    assert mock_chat.call_count == 2


def test_null_response_drops_note_silently(mock_chat, caplog):
    mock_chat.return_value = "null"
    with caplog.at_level(logging.WARNING, logger="noter.agents.synthesizer"):
        results = run(_SIMPLE_PLAN, [_make_source()])
    assert results == []
    assert any(
        r.levelno == logging.WARNING and "insufficient source content" in r.message
        for r in caplog.records
    )
