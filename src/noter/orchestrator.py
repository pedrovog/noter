import logging
import time
from pathlib import Path

import typer

from noter import cache
from noter.agents import linker, planner, searcher, synthesizer, writer
from noter.schemas import SynthesizedNote

logger = logging.getLogger(__name__)


def _progress(msg: str, quiet: bool) -> None:
    if not quiet:
        typer.echo(msg, err=True)


def run(
    topic: str,
    vault_path: str,
    user_urls: list[str],
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
    no_search: bool,
    quiet: bool = False,
) -> None:
    # Planner
    t0 = time.perf_counter()
    try:
        plan = planner.run(topic)
        note_titles = [n.title for n in plan.notes]
        logger.debug("Planner finished in %.2fs", time.perf_counter() - t0)
        logger.info("Planner produced %d note(s): %s", len(plan.notes), note_titles)
        _progress(f"[Planner]      {len(plan.notes)} note(s) planned — {note_titles}", quiet)
    except Exception as exc:
        logger.error("[Planner] failed, aborting run: %s", exc, exc_info=True)
        return

    # Searcher
    t0 = time.perf_counter()
    try:
        sources = searcher.run(plan, user_urls, n_sources, cache_ttl, no_cache, no_search)
        auto = sum(1 for s in sources if s.source == "auto")
        user_count = sum(1 for s in sources if s.source == "user")
        cached = sum(1 for s in sources if s.from_cache)
        logger.debug("Searcher finished in %.2fs", time.perf_counter() - t0)
        logger.info(
            "Searcher returned %d source(s): %d auto, %d user, %d cached",
            len(sources),
            auto,
            user_count,
            cached,
        )
        _progress(
            f"[Searcher]     {len(sources)} sources "
            f"({auto} automatic, {user_count} from user) — {cached} from cache",
            quiet,
        )
    except Exception as exc:
        logger.warning(
            "[Searcher] failed, continuing with empty source list: %s", exc, exc_info=True
        )
        sources = []
        _progress("[Searcher]     0 sources (failed — continuing with empty source list)", quiet)

    # Synthesizer
    t0 = time.perf_counter()
    synth_notes: list[SynthesizedNote] = []
    try:
        _progress("[Synthesizer]  Synthesizing...", quiet)
        synth_notes = synthesizer.run(plan, sources)
        logger.debug("Synthesizer finished in %.2fs", time.perf_counter() - t0)
        logger.info(
            "Synthesizer produced %d note(s) from %d planned",
            len(synth_notes),
            len(plan.notes),
        )
        dropped = len(plan.notes) - len(synth_notes)
        if dropped:
            logger.warning(
                "Synthesizer dropped %d note(s) for insufficient source content", dropped
            )
    except Exception as exc:
        logger.error(
            "[Synthesizer] failed after %d/%d note(s), aborting run: %s",
            len(synth_notes),
            len(plan.notes),
            exc,
            exc_info=True,
        )
        return

    # Writer
    t0 = time.perf_counter()
    try:
        note_paths = writer.run(synth_notes, vault_path)
        names = " | ".join(Path(p).name for p in note_paths)
        logger.debug("Writer finished in %.2fs", time.perf_counter() - t0)
        logger.info("Writer wrote %d note(s)", len(note_paths))
        _progress(f"[Writer]       {names}", quiet)
    except Exception as exc:
        logger.error("[Writer] failed, aborting run: %s", exc, exc_info=True)
        return

    # Linker
    t0 = time.perf_counter()
    try:
        n_links = linker.run(note_paths, vault_path)
        logger.debug("Linker finished in %.2fs", time.perf_counter() - t0)
        logger.info("Linker injected %d link(s)", n_links)
        _progress(f"[Linker]       {n_links} link(s) injected", quiet)
    except Exception as exc:
        logger.warning("[Linker] failed — notes are preserved: %s", exc, exc_info=True)

    # Register URL usage in cache
    if not no_cache:
        try:
            for source in sources:
                for note_path in note_paths:
                    cache.register_usage(source.url, note_path)
        except Exception as exc:
            logger.warning("Failed to register URL usage in cache: %s", exc, exc_info=True)

    _progress(f"\nDone. {len(note_paths)} note(s) in 00 - Inbox/ awaiting review.", quiet)
