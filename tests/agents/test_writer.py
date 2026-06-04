import json
from unittest.mock import MagicMock, patch

import anthropic
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
    msg = MagicMock()
    text = json.dumps(tags or ["rag", "ai", "nlp"])
    msg.content = [anthropic.types.TextBlock(type="text", text=text)]
    return msg


@pytest.fixture
def mock_anthropic():
    with patch("noter.agents.writer.anthropic.Anthropic") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def test_correct_frontmatter(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags(["rag", "ai", "nlp"])
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "inbox" / "RAG Architecture.md").read_text()
    assert "type: permanent" in content
    assert "created: " in content
    assert "tags: [rag, ai, nlp]" in content
    assert "sources:" in content


def test_filename_sanitization(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    run([_make_note(title="Atenção: RAG!")], str(tmp_path))
    assert (tmp_path / "inbox" / "Atencao RAG.md").exists()


def test_numeric_suffix_when_file_exists(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "RAG Architecture.md").write_text("existing")
    run([_make_note()], str(tmp_path))
    assert (inbox / "RAG Architecture.md").read_text() == "existing"
    assert (inbox / "RAG Architecture (2).md").exists()


def test_required_sections_present(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    run([_make_note()], str(tmp_path))
    content = (tmp_path / "inbox" / "RAG Architecture.md").read_text()
    assert "## Core Concept" in content
    assert "## Subtopics" in content
    assert "## Connections" in content
    assert "## Sources" in content


def test_sources_listed_correctly(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    sources = [
        SourceRef(url="https://a.com", title="Paper A"),
        SourceRef(url="https://b.com", title="Paper B"),
    ]
    run([_make_note(sources=sources)], str(tmp_path))
    content = (tmp_path / "inbox" / "RAG Architecture.md").read_text()
    assert "- [Paper A](https://a.com)" in content
    assert "- [Paper B](https://b.com)" in content


def test_default_inbox_unchanged(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    run([_make_note()], str(tmp_path))
    assert (tmp_path / "inbox" / "RAG Architecture.md").exists()


def test_writes_to_custom_inbox(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = _mock_tags()
    run([_make_note()], str(tmp_path), inbox="Notes/Drafts")
    assert (tmp_path / "Notes" / "Drafts" / "RAG Architecture.md").exists()


def test_tag_inference_failure_raises_writer_error(mock_anthropic, tmp_path):
    mock_anthropic.messages.create.return_value = MagicMock(
        content=[anthropic.types.TextBlock(type="text", text="not json at all")]
    )
    with pytest.raises(WriterError):
        run([_make_note()], str(tmp_path))
    assert mock_anthropic.messages.create.call_count == 2
