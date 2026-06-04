# noter

<p align="center">
  <img src="assets/noter.png" alt="noter logo" width="180" />
</p>

<p align="center">
  <a href="https://github.com/pedrovog/noter/actions/workflows/ci.yml"><img src="https://github.com/pedrovog/noter/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

> Research a topic and write permanent notes to your Obsidian vault — from a single command.

## What It Does

noter accepts a topic string, autonomously searches the web, scrapes and synthesizes multiple sources, and writes one or more structured `.md` notes directly into your Obsidian vault's `00 - Inbox/` folder. What normally takes 30–60 minutes of manual research, reading, and writing is reduced to a single CLI invocation.

Each generated note includes a YAML frontmatter block, a structured body organized by subtopics, a sources section, and `[[wikilinks]]` to related notes already in your vault. Notes land in `00 - Inbox/` for human review — noter never edits existing vault content.

## Features

- Parallel search across Firecrawl, arXiv, and Wikipedia
- SQLite-backed URL cache with configurable TTL — re-running the same topic within the window skips all network calls
- Multi-note generation for broad topics — the Planner decides how many notes a topic warrants
- Automatic `[[wikilink]]` injection referencing existing vault notes
- Obsidian-compatible YAML frontmatter with auto-inferred tags
- User-supplied URLs scraped and prioritized alongside automatic results
- Graceful degradation — a failed source is logged and skipped; the pipeline never aborts on a single error

## Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) (package manager)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Firecrawl API key](https://firecrawl.dev/)
- An existing Obsidian vault directory on the local filesystem

## Installation

```bash
git clone https://github.com/pedrovog/noter.git
cd noter
uv sync
cp .env.example .env
# Edit .env with your keys and vault path
```

`uv sync` creates a `.venv` and installs all runtime and dev dependencies. The `noter` command is available as `uv run noter`.

## Configuration

Copy `.env.example` to `.env` and fill in the required values.

### Required

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for all Claude calls |
| `FIRECRAWL_API_KEY` | Firecrawl API key for web search and scraping |
| `VAULT_PATH` | Absolute path to your Obsidian vault root directory |

`VAULT_PATH` must point to an existing directory. noter writes notes to `$VAULT_PATH/00 - Inbox/` and reads all other `.md` files in the vault to find `[[wikilink]]` candidates.

### Optional — Per-Agent Model Overrides

By default every agent uses `claude-sonnet-4-6`. Override per agent in `.env`:

| Variable | Default | Agent |
|---|---|---|
| `NOTER_PLANNER_MODEL` | `claude-sonnet-4-6` | Planner |
| `NOTER_SYNTHESIZER_MODEL` | `claude-sonnet-4-6` | Synthesizer |
| `NOTER_WRITER_MODEL` | `claude-haiku-4-5-20251001` | Writer |
| `NOTER_LINKER_MODEL` | `claude-haiku-4-5-20251001` | Linker |

The global fallback `NOTER_MODEL` applies to any agent whose specific variable is not set.

## Usage

```bash
uv run noter "TOPIC"
```

### CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--source URL`, `-s URL` | (none) | Add a URL to scrape alongside automatic results. Repeatable. |
| `--source-file PATH` | (none) | Path to a `.txt` file with one URL per line |
| `--sources N` | `5` | Maximum number of automatic sources to fetch (must be >= 1) |
| `--cache-ttl N` | `30` | Cache time-to-live in days |
| `--no-search` | off | Skip automatic web search; only scrape URLs from `--source` / `--source-file` |
| `--no-cache` | off | Bypass cache reads and writes for this run |
| `--verbose`, `-v` | off | Enable DEBUG logging |
| `--quiet`, `-q` | off | Suppress progress output (warnings and errors still shown) |

### Examples

Research a topic with automatic sources:

```bash
uv run noter "retrieval-augmented generation"
```

Add specific URLs alongside automatic search:

```bash
uv run noter "transformer attention mechanism" \
  --source https://arxiv.org/abs/1706.03762 \
  --source https://jalammar.github.io/illustrated-transformer/
```

Provide URLs from a file and skip automatic search entirely:

```bash
uv run noter "federated learning" --source-file my_links.txt --no-search
```

Increase the source limit and disable caching:

```bash
uv run noter "diffusion models" --sources 10 --no-cache
```

Shorten the cache TTL to force a fresher scrape next time:

```bash
uv run noter "LLM quantization" --cache-ttl 3
```

## Terminal Output

A typical run prints one line per pipeline stage:

```
[Planner]      2 note(s) planned — ['RAG Overview', 'RAG Architectures']
[Searcher]     8 sources (6 automatic, 2 from user) — 3 from cache
[Synthesizer]  Synthesizing...
[Writer]       RAG Overview.md | RAG Architectures.md
[Linker]       5 link(s) injected

Done. 2 note(s) in 00 - Inbox/ awaiting review.
```

## Architecture

noter is a sequential pipeline of five independent agents. The orchestrator is the only component that sequences agents — agents never call each other.

```
cli.py
  └─ orchestrator.run(topic, vault_path, user_urls, n_sources, cache_ttl, no_cache, no_search, quiet)
       ├─ planner.run(topic)               → PlannerOutput
       ├─ searcher.run(plan, user_urls, …) → list[SourceResult]
       ├─ synthesizer.run(plan, sources)   → list[SynthesizedNote]
       ├─ writer.run(synth_notes, vault)   → list[str]   # absolute paths
       └─ linker.run(note_paths, vault)    → int         # links injected
```

### Agents

| Agent | Responsibility |
|---|---|
| Planner | Decides how many notes to write, what subtopics each covers, and generates search queries |
| Searcher | Fetches sources via Firecrawl search, arXiv, and Wikipedia in parallel; serves cache hits first |
| Synthesizer | Sends scraped content to Claude and produces structured note drafts per `NoteSpec` |
| Writer | Renders drafts as `.md` files with YAML frontmatter; writes to `VAULT_PATH/00 - Inbox/` |
| Linker | Scans the vault for existing note titles and injects `[[wikilinks]]` into new notes in-place |

### Searcher Parallelism

Track A (automatic sources) and Track B (user-supplied URLs) run concurrently via `ThreadPoolExecutor`. Within Track A, Firecrawl queries, arXiv, and Wikipedia also run in parallel. Results are deduplicated and capped at `--sources`.

### Data Schemas

Pydantic v2 models in `src/noter/schemas.py` are the contracts between agents:

| Model | Description |
|---|---|
| `PlannerOutput` | Planner output — note specs, search queries, multi-note flag |
| `NoteSpec` | One planned note — title, subtopics, focus sentence |
| `SourceResult` | One fetched source — URL, content, origin (`auto`/`user`), cache flag |
| `SynthesizedNote` | Synthesizer output per note — core concept, subtopic content, source refs |
| `SourceRef` | URL + title pair used in the note's sources section |

### Cache

SQLite database at `~/.pesquisa/cache.db` (created automatically on first run, never requires setup).

| Table | Contents |
|---|---|
| `scrape_cache` | URL → scraped markdown content, expires after `cache_ttl` days |
| `url_usage` | URL → note path; used to warn when a URL has already been scraped into another note |

## Development

Install all dependencies including dev tools:

```bash
uv sync
```

Run the full test suite:

```bash
make test
# or: uv run pytest -v
```

Run a single test:

```bash
uv run pytest tests/test_cache.py::test_save_and_hit
```

Lint and auto-fix:

```bash
make lint    # ruff check only, no changes
make fix     # ruff check --fix + ruff format
```

Test individual agents against real APIs (requires a valid `.env`):

```bash
make planner topic="RAG"    # runs Planner, prints PlannerOutput JSON
make search topic="RAG"     # runs Planner + Searcher, prints SourceResult list JSON
```

### Makefile Targets

| Target | Description |
|---|---|
| `make install` | `uv sync` — install all dependencies |
| `make test` | `uv run pytest -v` — full test suite |
| `make coverage` | pytest with coverage report and HTML output |
| `make typecheck` | `uv run mypy src/noter/` — strict type checking |
| `make lint` | `ruff check src/ tests/` — lint only, no writes |
| `make fix` | `ruff check --fix` + `ruff format` — fix and format |
| `make run topic="…"` | `uv run noter "$(topic)"` — run noter |
| `make run-verbose topic="…"` | Run noter with `--verbose` flag |
| `make planner topic="…"` | Run Planner against the real API, print JSON |
| `make search topic="…"` | Run Planner + Searcher against real APIs, print JSON |

### Testing Conventions

- Cache tests pass `db_path=":memory:"` — no test touches `~/.pesquisa/cache.db`
- Agent tests mock `anthropic.Anthropic` and `firecrawl.FirecrawlApp` at the module level (e.g. `patch("noter.agents.planner.anthropic.Anthropic")`)
- Writer and Linker tests use `tmp_path` for all filesystem operations
- No test makes real network calls

## By Design

These are intentional constraints, not missing features:

| Limitation | Rationale |
|---|---|
| CLI only — no web UI, no API server | Single-user local tool |
| No Docker or containerization | Zero-infrastructure local install |
| SQLite only — no Redis, no Postgres | No external services required |
| Write-once to `00 - Inbox/` — no editing existing notes | Notes are for human review; automated overwriting is out of scope |
| No streaming LLM responses | Batch pipeline; all Claude output is structured JSON |
| Claude via Anthropic SDK only | No OpenAI, no local models |
| Firecrawl only for scraping | No Playwright, Selenium, or custom crawlers |
| No semantic search or vector embeddings | Out of scope |
| No scheduling or daemon mode | Invoked manually per topic |

## License

MIT — see [LICENSE](LICENSE).
