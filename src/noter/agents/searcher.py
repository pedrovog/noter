import json
import logging
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import firecrawl
from firecrawl.v2.types import ScrapeOptions

from noter import cache
from noter.exceptions import SearcherError  # noqa: F401
from noter.schemas import PlannerOutput, SourceResult

logger = logging.getLogger(__name__)


def run(
    plan: PlannerOutput,
    user_urls: list[str],
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
    no_search: bool,
) -> list[SourceResult]:
    """Collect raw content from automatic search and user-supplied URLs.

    Raises:
        SearcherError: if all sources fail and no content can be returned.
    """
    app = firecrawl.FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_b = pool.submit(_track_b, app, user_urls, cache_ttl, no_cache)
        future_a = (
            pool.submit(_track_a, app, plan, n_sources, cache_ttl, no_cache)
            if not no_search
            else None
        )
        track_b = future_b.result()
        track_a = future_a.result() if future_a is not None else []

    all_results = track_b + track_a

    if not no_cache:
        for r in all_results:
            if not r.from_cache:
                cache.save_cache(r.url, r.content)

    return all_results


def _track_a(
    app: firecrawl.FirecrawlApp,
    plan: PlannerOutput,
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
) -> list[SourceResult]:
    results: list[SourceResult] = []
    first_query = plan.search_queries[0] if plan.search_queries else plan.main_title

    with ThreadPoolExecutor() as pool:
        fc_futures = [
            pool.submit(_firecrawl_search, app, q, cache_ttl, no_cache) for q in plan.search_queries
        ]
        arxiv_future = pool.submit(_arxiv_search, first_query, cache_ttl, no_cache)
        wiki_future = pool.submit(_wikipedia_fetch, plan.main_title, cache_ttl, no_cache)

        for future in as_completed(fc_futures):
            try:
                results.extend(future.result())
            except Exception as exc:
                logger.warning("Firecrawl search failed: %s", exc)

        try:
            results.extend(arxiv_future.result())
        except Exception as exc:
            logger.warning("arXiv search failed: %s", exc)

        try:
            wiki = wiki_future.result()
            if wiki:
                results.append(wiki)
        except Exception as exc:
            logger.warning("Wikipedia fetch failed for %r: %s", plan.main_title, exc)

    # Deduplicate by URL and enforce n_sources limit
    if n_sources <= 0:
        return []
    seen: set[str] = set()
    limited: list[SourceResult] = []
    for r in results:
        if r.url not in seen:
            seen.add(r.url)
            limited.append(r)
            if len(limited) >= n_sources:
                break

    logger.debug(
        "Searcher track A: %d raw result(s) → %d after dedup/limit(%d)",
        len(results),
        len(limited),
        n_sources,
    )
    return limited


def _track_b(
    app: firecrawl.FirecrawlApp,
    user_urls: list[str],
    cache_ttl: int,
    no_cache: bool,
) -> list[SourceResult]:
    results: list[SourceResult] = []

    for url in user_urls:
        prior_notes = cache.check_duplicate(url)
        if prior_notes:
            titles = ", ".join(f"[[{p}]]" for p in prior_notes)
            logger.warning("%s already used in %s", url, titles)

        if not no_cache:
            cached = cache.get_cached(url, cache_ttl)
            if cached:
                logger.debug("Cache hit (user): %s", url)
                results.append(
                    SourceResult(url=url, title=url, content=cached, source="user", from_cache=True)
                )
                continue

        try:
            doc = app.scrape(url, formats=["markdown"])
            content = getattr(doc, "markdown", None) or ""
            meta = getattr(doc, "metadata", None)
            title = (getattr(meta, "title", None) if meta else None) or url
            logger.debug("Scraped %s (%d chars)", url, len(content))
            results.append(SourceResult(url=url, title=title, content=content, source="user"))
        except Exception as exc:
            logger.warning("Failed to scrape %s: %s", url, exc)

    return results


def _firecrawl_search(
    app: firecrawl.FirecrawlApp,
    query: str,
    cache_ttl: int,
    no_cache: bool,
) -> list[SourceResult]:
    try:
        data = app.search(query, limit=3, scrape_options=ScrapeOptions(formats=["markdown"]))
    except Exception as exc:
        logger.warning("Firecrawl search %r failed: %s", query, exc)
        return []

    results: list[SourceResult] = []
    for item in getattr(data, "web", None) or []:
        # Support both SearchResultWeb (url attr) and Document (metadata.url)
        url = getattr(item, "url", None)
        meta = getattr(item, "metadata", None)
        if not url and meta:
            url = getattr(meta, "url", None)
        if not url:
            continue

        if not no_cache:
            cached = cache.get_cached(url, cache_ttl)
            if cached:
                title = (
                    getattr(item, "title", None)
                    or (getattr(meta, "title", None) if meta else None)
                    or url
                )
                logger.debug("Cache hit (auto): %s", url)
                results.append(
                    SourceResult(
                        url=url, title=title, content=cached, source="auto", from_cache=True
                    )
                )
                continue

        # Document has .markdown; SearchResultWeb has .description
        content = getattr(item, "markdown", None) or getattr(item, "description", None) or ""
        title = (
            (getattr(meta, "title", None) if meta else None) or getattr(item, "title", None) or url
        )
        results.append(SourceResult(url=url, title=title, content=content, source="auto"))

    logger.debug("Firecrawl search %r returned %d result(s)", query, len(results))
    return results


def _parse_arxiv_xml(xml_content: str, from_cache: bool) -> list[SourceResult]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        logger.warning("arXiv XML parse failed: %s", exc)
        return []

    results: list[SourceResult] = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        id_el = entry.find("atom:id", ns)
        if title_el is None or summary_el is None or id_el is None:
            continue
        paper_url = (id_el.text or "").strip()
        title = (title_el.text or "").strip()
        content = f"# {title}\n\n{(summary_el.text or '').strip()}"
        results.append(
            SourceResult(
                url=paper_url, title=title, content=content, source="auto", from_cache=from_cache
            )  # noqa: E501
        )
    return results


def _arxiv_search(query: str, cache_ttl: int, no_cache: bool) -> list[SourceResult]:
    api_url = (
        f"http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&max_results=3"
    )

    if not no_cache:
        cached_xml = cache.get_cached(api_url, cache_ttl)
        if cached_xml is not None:
            logger.debug("Cache hit (arXiv): %r", query)
            return _parse_arxiv_xml(cached_xml, from_cache=True)

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "noter/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_content = resp.read().decode("utf-8")
    except Exception as exc:
        logger.warning("arXiv request failed: %s", exc)
        return []

    if not no_cache:
        cache.save_cache(api_url, xml_content)

    return _parse_arxiv_xml(xml_content, from_cache=False)


def _wikipedia_fetch(topic: str, cache_ttl: int, no_cache: bool) -> SourceResult | None:
    encoded = urllib.parse.quote(topic)
    page_url = f"https://en.wikipedia.org/wiki/{encoded}"
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    if not no_cache:
        cached = cache.get_cached(page_url, cache_ttl)
        if cached:
            logger.debug("Cache hit (Wikipedia): %r", topic)
            return SourceResult(
                url=page_url, title=topic, content=cached, source="auto", from_cache=True
            )

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "noter/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Wikipedia request failed for %r: %s", topic, exc)
        return None

    if data.get("type") == "disambiguation" or not data.get("extract"):
        return None

    title = data.get("title", topic)
    content = f"# {title}\n\n{data['extract']}"
    return SourceResult(url=page_url, title=title, content=content, source="auto")
