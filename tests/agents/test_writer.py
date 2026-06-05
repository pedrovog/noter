import json
from unittest.mock import patch

import pytest

from noter.agents.writer import run
from noter.exceptions import WriterError
from noter.schemas import SourceRef, SubtopicContent, SynthesizedNote


def _make_note(
    title="RAG Architecture",
    core_concept="RAG combines retrieval with generation.",
    subtopics=None,
    sources=None,
):
    return SynthesizedNote(
        note_title=title,
        core_concept=core_concept,
        subtopics=subtopics or [SubtopicContent(title="Retrieval", content="Vectors are queried.")],
        sources_used=sources or [SourceRef(url="https://example.com", title="RAG Paper")],
    )


def _mock_tags(tags=None):
    return json.dumps(tags or ["rag", "ai", "nlp"])


@pytest.fixture
def mock_chat():
    with patch("noter.agents.writer.chat") as chat:
        yield chat


def test_correct_frontmatter(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags(["rag", "ai", "nlp"])
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "noter" / "RAG Architecture.md").read_text()
    assert "type: permanent" in content
    assert "created: " in content
    assert "tags: [rag, ai, nlp]" in content
    assert "sources:" in content


def test_filename_sanitization(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    run([_make_note(title="Atenção: RAG!")], str(tmp_path))
    assert (tmp_path / "noter" / "Atencao RAG.md").exists()


def test_numeric_suffix_when_file_exists(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    inbox = tmp_path / "noter"
    inbox.mkdir(parents=True)
    (inbox / "RAG Architecture.md").write_text("existing")
    run([_make_note()], str(tmp_path))
    assert (inbox / "RAG Architecture.md").read_text() == "existing"
    assert (inbox / "RAG Architecture (2).md").exists()


def test_required_sections_present(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "noter" / "RAG Architecture.md").read_text()
    assert "## Core Concept" in content
    assert "## Subtopics" in content
    assert "## Connections" in content
    assert "## Sources" in content


def test_sources_listed_correctly(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    sources = [
        SourceRef(url="https://a.com", title="Paper A"),
        SourceRef(url="https://b.com", title="Paper B"),
    ]
    run([_make_note(sources=sources)], str(tmp_path))
    content = (tmp_path / "noter" / "RAG Architecture.md").read_text()
    assert "- [Paper A](https://a.com)" in content
    assert "- [Paper B](https://b.com)" in content


def test_default_inbox_unchanged(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    run([_make_note()], str(tmp_path))
    assert (tmp_path / "noter" / "RAG Architecture.md").exists()


def test_writes_to_custom_inbox(mock_chat, tmp_path):
    mock_chat.return_value = _mock_tags()
    run([_make_note()], str(tmp_path), inbox="Notes/Drafts")
    assert (tmp_path / "Notes" / "Drafts" / "RAG Architecture.md").exists()


def test_tag_inference_failure_raises_writer_error(mock_chat, tmp_path):
    mock_chat.return_value = "not json at all"
    with pytest.raises(WriterError):
        run([_make_note()], str(tmp_path))
    assert mock_chat.call_count == 2


def test_tags_extracted_from_markdown_fence(mock_chat, tmp_path):
    # Many models wrap the array in a ```json fence despite the prompt.
    mock_chat.return_value = '```json\n["rag", "ai", "nlp"]\n```'
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "noter" / "RAG Architecture.md").read_text()
    assert "tags: [rag, ai, nlp]" in content


def test_tags_extracted_with_preamble(mock_chat, tmp_path):
    mock_chat.return_value = 'Here are the tags: ["rag", "ai"]'
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "noter" / "RAG Architecture.md").read_text()
    assert "tags: [rag, ai]" in content
