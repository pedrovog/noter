import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from noter.agents.linker import _build_index, run


def _make_vault(tmp_path: Path, notes: dict[str, str]) -> None:
    for name, content in notes.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _make_note_content(title: str, body_text: str) -> str:
    return (
        f"---\ntype: permanent\ncreated: 2026-05-28\ntags: []\n---\n\n"
        f"# {title}\n\n## Core Concept\n\n{body_text}\n\n"
        f"## Connections\n\n<!-- filled by Linker -->\n\n## Sources\n\n"
    )


def _note_body(content: str) -> str:
    """Return note content up to (not including) ## Connections."""
    return content.split("## Connections")[0] if "## Connections" in content else content


def _mock_links(titles: list[str]) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps({"titles_to_link": titles}))]
    return msg


@pytest.fixture
def mock_anthropic():
    with patch("noter.agents.linker.anthropic.Anthropic") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def test_indexer_finds_all_titles(tmp_path):
    _make_vault(
        tmp_path,
        {
            "RAG.md": "# RAG\n\ncontent",
            "Vector Databases.md": "# Vector Databases\n\ncontent",
            "subdir/Knowledge Graphs.md": "# Knowledge Graphs\n\ncontent",
        },
    )
    index = _build_index(str(tmp_path))
    assert "RAG" in index
    assert "Vector Databases" in index
    assert "Knowledge Graphs" in index


def test_link_injected_on_first_occurrence(mock_anthropic, tmp_path):
    _make_vault(tmp_path, {"RAG.md": "# RAG\n\nretrieval augmented generation"})
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "Intro to AI.md"
    note_path.write_text(_make_note_content("Intro to AI", "RAG is great. RAG stands for..."))

    mock_anthropic.messages.create.return_value = _mock_links(["RAG"])
    run([str(note_path)], str(tmp_path))

    content = note_path.read_text()
    assert "[[RAG]]" in content
    assert _note_body(content).count("[[RAG]]") == 1


def test_no_self_reference(mock_anthropic, tmp_path):
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "RAG.md"
    note_path.write_text(_make_note_content("RAG", "RAG is retrieval augmented generation."))

    count = run([str(note_path)], str(tmp_path))

    assert count == 0
    assert "[[RAG]]" not in note_path.read_text()
    mock_anthropic.messages.create.assert_not_called()


def test_no_duplicate_links_in_body(mock_anthropic, tmp_path):
    _make_vault(tmp_path, {"Embeddings.md": "# Embeddings\n\nvector representations"})
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "RAG.md"
    note_path.write_text(
        _make_note_content("RAG", "Embeddings are used in RAG. Embeddings represent text.")
    )

    mock_anthropic.messages.create.return_value = _mock_links(["Embeddings"])
    run([str(note_path)], str(tmp_path))

    assert _note_body(note_path.read_text()).count("[[Embeddings]]") == 1


def test_connections_section_filled(mock_anthropic, tmp_path):
    _make_vault(
        tmp_path,
        {
            "RAG.md": "# RAG\n\ncontent",
            "Embeddings.md": "# Embeddings\n\ncontent",
        },
    )
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "Vector Search.md"
    note_path.write_text(_make_note_content("Vector Search", "RAG uses Embeddings for retrieval."))

    mock_anthropic.messages.create.return_value = _mock_links(["RAG", "Embeddings"])
    run([str(note_path)], str(tmp_path))

    content = note_path.read_text()
    assert "- [[RAG]]" in content
    assert "- [[Embeddings]]" in content
    assert "<!-- filled by Linker -->" not in content


def test_no_possible_links_does_not_fail(mock_anthropic, tmp_path):
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "Unrelated Note.md"
    note_path.write_text(
        _make_note_content("Unrelated Note", "This note has no connections to vault.")
    )

    count = run([str(note_path)], str(tmp_path))

    assert count == 0
    assert "<!-- filled by Linker -->" in note_path.read_text()
    mock_anthropic.messages.create.assert_not_called()


def test_detect_links_retries_on_bad_json(mock_anthropic, tmp_path):
    _make_vault(tmp_path, {"RAG.md": "# RAG\n\ncontent"})
    inbox = tmp_path / "00 - Inbox"
    inbox.mkdir()
    note_path = inbox / "Intro.md"
    note_path.write_text(_make_note_content("Intro", "RAG is a retrieval technique."))

    bad = MagicMock()
    bad.content = [MagicMock(text="not json at all")]
    mock_anthropic.messages.create.side_effect = [bad, _mock_links(["RAG"])]

    run([str(note_path)], str(tmp_path))

    assert mock_anthropic.messages.create.call_count == 2
    assert "[[RAG]]" in note_path.read_text()
