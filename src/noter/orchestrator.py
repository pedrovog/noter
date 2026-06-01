import logging
from pathlib import Path

from noter import cache
from noter.agents import linker, planner, searcher, synthesizer, writer

logger = logging.getLogger(__name__)


def run(
    topic: str,
    vault_path: str,
    user_urls: list[str],
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
    no_search: bool,
) -> None:
    # Planner
    try:
        plan = planner.run(topic)
        note_titles = [n.title for n in plan.notes]
        print(f"[Planner]      {len(plan.notes)} note(s) planned — {note_titles}")
    except Exception as exc:
        logger.warning("[Planner] failed: %s", exc)
        return

    # Searcher
    try:
        sources = searcher.run(plan, user_urls, n_sources, cache_ttl, no_cache, no_search)
        auto = sum(1 for s in sources if s.source == "auto")
        user_count = sum(1 for s in sources if s.source == "user")
        cached = sum(1 for s in sources if s.from_cache)
        print(
            f"[Searcher]     {len(sources)} sources "
            f"({auto} automatic, {user_count} from user) — {cached} from cache"
        )
    except Exception as exc:
        logger.warning("[Searcher] failed: %s", exc)
        sources = []
        print("[Searcher]     0 sources (failed — continuing with empty source list)")

    # Synthesizer
    try:
        print("[Synthesizer]  Synthesizing...")
        synth_notes = synthesizer.run(plan, sources)
    except Exception as exc:
        logger.warning("[Synthesizer] failed: %s", exc)
        return

    # Writer
    try:
        note_paths = writer.run(synth_notes, vault_path)
        names = " | ".join(Path(p).name for p in note_paths)
        print(f"[Writer]       {names}")
    except Exception as exc:
        logger.warning("[Writer] failed: %s", exc)
        return

    # Linker
    try:
        n_links = linker.run(note_paths, vault_path)
        print(f"[Linker]       {n_links} link(s) injected")
    except Exception as exc:
        logger.warning("[Linker] failed: %s — notes are preserved", exc)

    # Register URL usage in cache
    if not no_cache:
        for source in sources:
            for note_path in note_paths:
                cache.register_usage(source.url, note_path)

    print(f"\nDone. {len(note_paths)} note(s) in 00 - Inbox/ awaiting review.")
