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
- `--version` flag: prints `noter <version>` via `importlib.metadata` and exits
- `--verbose` / `-v` flag: sets log level to DEBUG for tracing sources, cache hits, etc.

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
