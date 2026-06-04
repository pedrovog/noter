from unittest.mock import MagicMock, patch

import pytest

from noter.agents.searcher import run
from noter.schemas import NoteSpec, PlannerOutput


@pytest.fixture
def plan():
    return PlannerOutput(
        main_title="Backpropagation",
        generate_multiple_notes=False,
        notes=[NoteSpec(title="Backpropagation", subtopics=["gradients"], focus="basics")],
        search_queries=["backpropagation gradient descent", "chain rule neural network"],
    )


def _scrape_doc(url: str, title: str = "Page Title", content: str = "page content") -> MagicMock:
    doc = MagicMock()
    doc.markdown = content
    doc.metadata = MagicMock()
    doc.metadata.url = url
    doc.metadata.title = title
    return doc


def _search_data(items: list) -> MagicMock:
    data = MagicMock()
    data.web = items
    return data


def _search_item(url: str, title: str = "Result", description: str = "desc") -> MagicMock:
    item = MagicMock(spec=[])  # no attrs by default — duck typing safe
    item.url = url
    item.title = title
    item.description = description
    item.markdown = None
    item.metadata = None
    return item


@pytest.fixture
def mock_firecrawl():
    with patch("noter.agents.searcher.firecrawl.FirecrawlApp") as cls:
        app = MagicMock()
        cls.return_value = app
        # Default: search returns empty, scrape raises to avoid accidental network calls
        app.search.return_value = _search_data([])
        app.scrape.side_effect = Exception("scrape not configured in this test")
        yield app


@pytest.fixture
def mock_cache(mocker):
    mocker.patch("noter.agents.searcher.cache.get_cached", return_value=None)
    mocker.patch("noter.agents.searcher.cache.save_cache")
    mocker.patch("noter.agents.searcher.cache.check_duplicate", return_value=[])


@pytest.fixture
def mock_external(mocker):
    """Silence arXiv and Wikipedia HTTP calls."""
    mocker.patch(
        "noter.agents.searcher.urllib.request.urlopen", side_effect=Exception("no network")
    )


def test_user_url_always_included(plan, mock_firecrawl, mock_cache, mock_external):
    mock_firecrawl.scrape.side_effect = None
    mock_firecrawl.scrape.return_value = _scrape_doc(
        "https://user.com", "User Page", "user content"
    )  # noqa: E501

    results = run(
        plan, ["https://user.com"], n_sources=5, cache_ttl=30, no_cache=False, no_search=True
    )

    urls = [r.url for r in results]
    assert "https://user.com" in urls
    assert all(r.source == "user" for r in results)


def test_sources_limit_respected(plan, mock_firecrawl, mock_cache, mock_external, mocker):
    items = [_search_item(f"https://result{i}.com") for i in range(10)]
    mock_firecrawl.search.return_value = _search_data(items)

    results = run(plan, [], n_sources=2, cache_ttl=30, no_cache=False, no_search=False)

    auto_results = [r for r in results if r.source == "auto"]
    assert len(auto_results) <= 2


def test_cache_hit_avoids_scraping(plan, mock_firecrawl, mock_cache, mock_external, mocker):
    mocker.patch(
        "noter.agents.searcher.cache.get_cached",
        return_value="cached content",
    )

    results = run(
        plan, ["https://cached.com"], n_sources=0, cache_ttl=30, no_cache=False, no_search=True
    )

    assert any(r.url == "https://cached.com" and r.from_cache for r in results)
    mock_firecrawl.scrape.assert_not_called()


def test_duplicate_url_warning(plan, mock_firecrawl, mock_cache, mock_external, mocker, caplog):
    mocker.patch(
        "noter.agents.searcher.cache.check_duplicate",
        return_value=["/vault/old-note.md"],
    )
    mock_firecrawl.scrape.side_effect = None
    mock_firecrawl.scrape.return_value = _scrape_doc("https://dup.com")

    import logging

    with caplog.at_level(logging.WARNING, logger="noter.agents.searcher"):
        run(plan, ["https://dup.com"], n_sources=0, cache_ttl=30, no_cache=False, no_search=True)

    assert "https://dup.com" in caplog.text
    assert "already used" in caplog.text


def test_one_url_failure_does_not_interrupt_search(plan, mock_firecrawl, mock_cache, mock_external):
    mock_firecrawl.scrape.side_effect = [
        Exception("connection refused"),
        _scrape_doc("https://good.com", "Good Page", "good content"),
    ]

    results = run(
        plan,
        ["https://bad.com", "https://good.com"],
        n_sources=0,
        cache_ttl=30,
        no_cache=False,
        no_search=True,
    )

    urls = [r.url for r in results]
    assert "https://bad.com" not in urls
    assert "https://good.com" in urls


def test_no_search_skips_automatic_track(plan, mock_firecrawl, mock_cache, mock_external):
    run(plan, [], n_sources=5, cache_ttl=30, no_cache=False, no_search=True)

    mock_firecrawl.search.assert_not_called()
