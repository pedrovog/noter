# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `.github/workflows/ci.yml` — CI pipeline running `ruff check` and `pytest` on every push and PR
- `.pre-commit-config.yaml` — pre-commit hooks for `ruff check --fix`, `ruff-format`, and `mypy` (local hook via `uv run mypy src/noter/`)
- `LICENSE` — MIT license; README updated accordingly
- `pytest-cov` dev dependency; `--cov=noter --cov-report=term-missing` added to default pytest options; `make coverage` target added
- `mypy` dev dependency with `strict = true`; `[tool.mypy]` config in `pyproject.toml`; `make typecheck` target added; all type errors fixed across agents and cache
- `tests/conftest.py` — `reset_connections` autouse fixture moved here from `test_cache.py` so it's available to all test modules
- `--version` flag: prints `noter <version>` via `importlib.metadata` and exits
- `--verbose` / `-v` flag: sets log level to DEBUG for tracing sources, cache hits, etc.
- `--quiet` / `-q` flag: suppresses progress output, keeps WARNING+ visible (not ERROR-only)

### Changed
- Logging overhauled across the pipeline: `DEBUG` statements added to all agents (retry attempts, cache hits, timings, per-note detail); fatal stage failures now log `ERROR` with traceback; synthesizer silently-dropped notes now log `WARNING`; duplicate-URL `print` in searcher converted to `logger.warning`; verbose mode swaps to a richer format with timestamp, thread name, and module name; third-party loggers (`httpx`, `httpcore`, `anthropic`, `urllib3`, `firecrawl`) clamped to `WARNING` in verbose mode; progress output routed through `_progress()` helper respecting `--quiet`
- Searcher failure logging: single log point per failure (removed double-logging); `exc_info=True` added to all WARNING calls so tracebacks appear under `--verbose`; `_firecrawl_search`, `_arxiv_search`, `_wikipedia_fetch` now raise on network errors, caught by `_track_a`
- Synthesizer abort log now includes completed/total note count (e.g. "failed after 2/4 note(s)")
- `_detect_links` warning now includes the note filename for multi-note correlation
- `cache.register_usage` loop guarded with `try/except` + WARNING log
- `caplog` assertions added for Planner/Synthesizer/Writer ERROR abort paths and Synthesizer dropped-note WARNING (orchestrator coverage 84% → 96%)

## [0.1.0] - 2026-06-03

### Added
- Initial CLI pipeline: `planner → searcher → synthesizer → writer → linker`
- Obsidian markdown output with YAML frontmatter to `VAULT_PATH/00 - Inbox/`
- SQLite cache at `~/.pesquisa/cache.db` with TTL-based scrape cache and URL usage tracking
- Parallel searcher (Firecrawl + arXiv + Wikipedia) with user URL support
- Pydantic v2 schemas shared across the pipeline
- Per-agent model overrides via `NOTER_*_MODEL` env vars
- `pyproject.toml` project metadata and `uv` dependency management
- Project logo and README

[Unreleased]: https://github.com/pedrovog/noter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pedrovog/noter/releases/tag/v0.1.0
