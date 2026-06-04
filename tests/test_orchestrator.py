import logging
from unittest.mock import patch

import pytest

from noter.orchestrator import run
from noter.schemas import (
    NoteSpec,
    PlannerOutput,
    SourceRef,
    SourceResult,
    SubtopicContent,
    SynthesizedNote,
)


def _make_plan() -> PlannerOutput:
    return PlannerOutput(
        main_title="RAG",
        generate_multiple_notes=False,
        notes=[NoteSpec(title="RAG", subtopics=["retrieval"], focus="overview")],
        search_queries=["retrieval augmented generation"],
    )


def _make_sources() -> list[SourceResult]:
    return [
        SourceResult(url="https://a.com", title="A", content="a", source="auto", from_cache=False),
        SourceResult(url="https://b.com", title="B", content="b", source="user", from_cache=True),
    ]


def _make_synth() -> list[SynthesizedNote]:
    return [
        SynthesizedNote(
            note_title="RAG",
            core_concept="Retrieval Augmented Generation",
            subtopics=[SubtopicContent(title="Overview", content="RAG overview.")],
            sources_used=[SourceRef(url="https://a.com", title="A")],
        )
    ]


@pytest.fixture
def all_mocks(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note_path = str(vault / "RAG.md")
    with (
        patch("noter.orchestrator.planner.run", return_value=_make_plan()) as mock_planner,
        patch("noter.orchestrator.searcher.run", return_value=_make_sources()) as mock_searcher,
        patch("noter.orchestrator.synthesizer.run", return_value=_make_synth()) as mock_synth,
        patch("noter.orchestrator.writer.run", return_value=[note_path]) as mock_writer,
        patch("noter.orchestrator.linker.run", return_value=2) as mock_linker,
        patch("noter.orchestrator.cache.register_usage") as mock_cache,
    ):
        yield {
            "planner": mock_planner,
            "searcher": mock_searcher,
            "synthesizer": mock_synth,
            "writer": mock_writer,
            "linker": mock_linker,
            "cache": mock_cache,
            "vault": str(vault),
        }


def test_full_flow_correct_sequence(all_mocks):
    run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    all_mocks["planner"].assert_called_once_with("RAG")
    all_mocks["searcher"].assert_called_once()
    all_mocks["synthesizer"].assert_called_once()
    all_mocks["writer"].assert_called_once()
    all_mocks["linker"].assert_called_once()


def test_urls_registered_in_cache_after_writing(all_mocks):
    run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    # 2 sources × 1 note path = 2 register_usage calls
    assert all_mocks["cache"].call_count == 2


def test_planner_failure_logs_error_and_aborts(all_mocks, caplog):
    all_mocks["planner"].side_effect = Exception("API error")
    with caplog.at_level(logging.ERROR):
        run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    assert any(r.levelno == logging.ERROR and "Planner" in r.message for r in caplog.records)
    all_mocks["synthesizer"].assert_not_called()
    all_mocks["writer"].assert_not_called()


def test_synthesizer_failure_logs_error_and_aborts(all_mocks, caplog):
    all_mocks["synthesizer"].side_effect = Exception("parse error")
    with caplog.at_level(logging.ERROR):
        run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    assert any(r.levelno == logging.ERROR and "Synthesizer" in r.message for r in caplog.records)
    all_mocks["writer"].assert_not_called()


def test_writer_failure_logs_error_and_aborts(all_mocks, caplog):
    all_mocks["writer"].side_effect = Exception("disk full")
    with caplog.at_level(logging.ERROR):
        run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    assert any(r.levelno == logging.ERROR and "Writer" in r.message for r in caplog.records)
    all_mocks["linker"].assert_not_called()
    all_mocks["cache"].assert_not_called()


def test_searcher_failure_propagates_error(all_mocks, caplog):
    all_mocks["searcher"].side_effect = Exception("network error")
    with caplog.at_level(logging.WARNING):
        run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    assert "Searcher" in caplog.text
    # synthesizer still called, but with empty sources list
    sources_arg = all_mocks["synthesizer"].call_args[0][1]
    assert sources_arg == []


def test_linker_failure_does_not_delete_notes(all_mocks, caplog):
    all_mocks["linker"].side_effect = Exception("vault read error")
    with caplog.at_level(logging.WARNING):
        run("RAG", all_mocks["vault"], [], 5, 30, False, False)
    assert "Linker" in caplog.text
    all_mocks["writer"].assert_called_once()
    assert all_mocks["cache"].call_count == 2
