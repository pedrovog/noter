# noter — Implementation Roadmap

Ordered by dependency. Each step must pass its tests before moving to the next.
Legend: `[x]` done · `[ ]` todo · `[~]` exists but needs rework

---

## Phase 1 — Foundation

- [x] `pyproject.toml` with all dependencies declared (build backend: `setuptools.build_meta`, dev deps via `[dependency-groups]`)
- [x] `uv sync` — `.venv` created, 44 packages installed
- [x] Directory structure: `src/noter/agents/`, `tests/agents/`
- [x] `cache.py` — all four functions implemented
- [x] `tests/test_cache.py` — 5 passing tests with `:memory:`
- [x] `.env.example` with `ANTHROPIC_API_KEY`, `FIRECRAWL_API_KEY`, `VAULT_PATH`
- [x] `src/noter/schemas.py` — Pydantic v2 models: `NoteSpec`, `PlannerOutput`, `SourceResult`, `SubtopicContent`, `SynthesizedNote`

---

## Phase 2 — CLI + Orchestrator Skeleton

> Goal: `noter --help` works; pipeline wired even if agents raise `NotImplementedError`.

- [x] `cli.py` — needs rework:
  - [x] Rename argument `tema` → `topic`; all help strings in English
  - [x] Validate `--source-file` path exists
  - [x] Validate each URL matches `^https?://`
  - [x] Validate `--sources >= 1`
  - [x] Validate `VAULT_PATH` env var points to an existing directory
  - [x] Call `orchestrator.run(...)` instead of `raise NotImplementedError`

- [x] `orchestrator.py` — needs rework:
  - [x] Fix signature to match spec: `run(topic, user_urls, n_sources, cache_ttl, no_cache, no_search)`
  - [x] Add progress `print()` statements for each stage
  - [x] Add per-agent error handling (log + continue, not crash)
  - [x] Register URL usage after all notes are written

---

## Phase 3 — Planner Agent

> Spec: `docs/specs/agent-planner.md`

- [x] Write Planner prompt (system + user template)
- [x] Implement `planner.run(topic: str) -> PlannerOutput` with Claude JSON call
- [x] One retry on invalid JSON → raise `PlannerError`
- [x] `tests/agents/test_planner.py`:
  - [x] `test_simple_topic_generates_one_note`
  - [x] `test_broad_topic_generates_multiple_notes`
  - [x] `test_search_queries_generated`
  - [x] `test_invalid_output_raises_exception`

---

## Phase 4 — Searcher Agent

> Spec: `docs/specs/agent-searcher.md`

- [x] Implement cache lookup before any external call
- [x] Track B: scrape user URLs via Firecrawl `/scrape`; duplicate URL warning via `check_duplicate`
- [x] Track A — Firecrawl `/search` for each query
- [x] Track A — arXiv API: search by term, return abstracts + links
- [x] Track A — Wikipedia API: fetch main article if it exists
- [x] Parallel execution: Tracks A and B via `ThreadPoolExecutor`; queries within Track A also parallel
- [x] Respect `n_sources` limit across all Track A sub-sources
- [x] Save new (non-cached) results to `scrape_cache`
- [x] Skip `--no-search` flag skips Track A entirely
- [x] `tests/agents/test_searcher.py`:
  - [x] `test_user_url_always_included`
  - [x] `test_sources_limit_respected`
  - [x] `test_cache_hit_avoids_scraping`
  - [x] `test_duplicate_url_warning`
  - [x] `test_one_url_failure_does_not_interrupt_search`
  - [x] `test_no_search_skips_automatic_track`

---

## Phase 5 — Synthesizer Agent

> Spec: `docs/specs/agent-synthesizer.md`

- [x] Implement source truncation to ~3000 tokens each
- [x] Prioritize user sources when total context exceeds limit
- [x] Write Synthesizer prompt following `focus` from each `NoteSpec`
- [x] Implement `synthesizer.run(plan, sources) -> list[SynthesizedNote]` with Claude JSON call
- [x] `tests/agents/test_synthesizer.py`:
  - [x] `test_user_sources_prioritized_in_context`
  - [x] `test_truncation_respects_token_limit`
  - [x] `test_multiple_notes_generated_for_broad_topic`
  - [x] `test_one_note_output_for_simple_topic`

---

## Phase 6 — Writer Agent

> Spec: `docs/specs/agent-writer.md`

- [x] Implement note template as Python string
- [x] File name sanitization (strip special chars)
- [x] No-overwrite logic: append ` (2)`, ` (3)` if file exists
- [x] Tag inference via Claude (3–5 lowercase tags from title + concept)
- [x] Write files to `VAULT_PATH/00 - Inbox/`
- [x] Return list of absolute paths created
- [x] `tests/agents/test_writer.py` (filesystem in `tmp_path`, Claude mocked):
  - [x] `test_correct_frontmatter`
  - [x] `test_filename_sanitization`
  - [x] `test_numeric_suffix_when_file_exists`
  - [x] `test_required_sections_present`
  - [x] `test_sources_listed_correctly`

---

## Phase 7 — Linker Agent

> Spec: `docs/specs/agent-linker.md`

- [x] Vault indexer: recursively read all `.md`, extract titles, build `dict[title, path]`
- [x] Write Linker prompt: note content + title list → substitutions JSON
- [x] Apply substitutions in-place (first occurrence only, no self-reference)
- [x] Fill `## Connections` section with linked titles
- [x] `tests/agents/test_linker.py` (vault in `tmp_path`, Claude mocked):
  - [x] `test_indexer_finds_all_titles`
  - [x] `test_link_injected_on_first_occurrence`
  - [x] `test_no_self_reference`
  - [x] `test_no_duplicate_links_in_body`
  - [x] `test_connections_section_filled`
  - [x] `test_no_possible_links_does_not_fail`

---

## Phase 8 — Orchestrator (full)

> Spec: `docs/specs/orchestrator.md`

- [x] Implement full `orchestrator.run()` with correct sequence and signatures
- [x] Terminal progress output matching the expected format in spec
- [x] Per-agent error handling: log warning + continue (never crash pipeline)
- [x] `cache.register_usage()` called for every `(source, note_path)` pair after writing
- [x] `tests/test_orchestrator.py` (all agents mocked):
  - [x] `test_full_flow_correct_sequence`
  - [x] `test_urls_registered_in_cache_after_writing`
  - [x] `test_searcher_failure_propagates_error`
  - [x] `test_linker_failure_does_not_delete_notes`

---

## Phase 9 — Integration

- [x] Choose 3 real vault topics: one simple, one medium, one broad
- [x] Run end-to-end for each; manually verify:
  - [x] Frontmatter is valid YAML with correct fields
  - [x] `[[wikilinks]]` point to existing vault notes
  - [x] Second run of the same topic hits cache (no Firecrawl calls)
  - [x] `--source` with a previously used URL triggers duplicate warning
- [x] Fix any issues found before closing this phase

---

## Current State Summary

| Component | Status |
|---|---|
| `pyproject.toml` | Done |
| `cache.py` + tests | Done |
| `.env.example` | Missing |
| `schemas.py` | Missing |
| `cli.py` | Needs rework |
| `orchestrator.py` | Needs rework |
| `planner.py` | Stub |
| `searcher.py` | Stub |
| `synthesizer.py` | Stub |
| `writer.py` | Stub |
| `linker.py` | Stub |
| Agent tests | Placeholder skips |
