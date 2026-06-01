# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install all deps including dev
uv run pytest                    # full test suite
uv run pytest tests/test_cache.py::test_save_and_hit  # single test
uv run noter "topic to research" # run the CLI
uv add <package>                 # add runtime dependency
uv add --dev <package>           # add dev dependency

# Makefile shortcuts
make test                        # uv run pytest -v
make lint                        # ruff check only
make fix                         # ruff check --fix + format
make planner topic="RAG"         # test planner against real API
make search topic="RAG"          # test planner → searcher against real APIs
```

**After every code write or edit:**
```bash
uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/
```

## CLI flags

```
uv run noter "topic" [OPTIONS]

  -s, --source URL        Add a user URL (repeatable)
  --source-file FILE      .txt file with one URL per line
  --sources INT           Max automatic sources (default: 5)
  --cache-ttl INT         Cache TTL in days (default: 30)
  --no-cache              Bypass cache reads and writes
  --no-search             Skip automatic web search (use only user URLs)
```

## Environment

Copy `.env.example` → `.env` and fill in:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API |
| `FIRECRAWL_API_KEY` | Web scraping |
| `VAULT_PATH` | Absolute path to Obsidian vault root |

Model overrides (optional, all default to `claude-sonnet-4-6`):

| Variable | Scope |
|---|---|
| `NOTER_MODEL` | Global default for all agents |
| `NOTER_PLANNER_MODEL` | Planner only |
| `NOTER_SYNTHESIZER_MODEL` | Synthesizer only |
| `NOTER_WRITER_MODEL` | Writer only |
| `NOTER_LINKER_MODEL` | Linker only |

SQLite cache lives at `~/.pesquisa/cache.db` (created automatically).

## Architecture

noter is a CLI pipeline: research a topic → write permanent notes to `VAULT_PATH/00 - Inbox/`.

```
cli.py
  └─ orchestrator.run(topic, vault_path, user_urls, n_sources, cache_ttl, no_cache, no_search)
       ├─ planner.run(topic)               → PlannerOutput
       ├─ searcher.run(plan, user_urls, …) → list[SourceResult]
       ├─ synthesizer.run(plan, sources)   → list[SynthesizedNote]
       ├─ writer.run(synth_notes, vault)   → list[str]   # absolute paths
       └─ linker.run(note_paths, vault)    → int         # links injected
```

**Agents** (`src/noter/agents/`) are plain modules — a `run()` function, no classes.
**Orchestrator** is the only component that sequences agents. Agents do not call each other.
**Per-agent error handling**: Firecrawl failures are logged and skipped; Claude JSON parse errors retry once then skip. Linker failure never deletes already-written notes.

### Key modules

- `schemas.py` — Pydantic v2 models shared across the pipeline: `NoteSpec`, `PlannerOutput`, `SourceResult`, `SubtopicContent`, `SourceRef`, `SynthesizedNote`
- `config.py` — Claude model selection; reads `NOTER_*_MODEL` env vars with `claude-sonnet-4-6` as global default
- `cache.py` — SQLite, two tables: `scrape_cache` (URL → markdown, TTL-based) and `url_usage` (URL → note path, for duplicate warnings). Uses a module-level `_connections` dict to keep `:memory:` connections alive across calls.
- `exceptions.py` — `PlannerError`, `SearcherError`, `SynthesizerError`, `WriterError`, `LinkerError`

### Searcher parallelism

Tracks A (automatic) and B (user URLs) run concurrently via `ThreadPoolExecutor`. Within Track A, Firecrawl queries + arXiv + Wikipedia also run in parallel. Firecrawl v2 API: `app.scrape(url, formats=["markdown"])` → `Document`; `app.search(query, limit=n, scrape_options=ScrapeOptions(formats=["markdown"]))` → `SearchData`.

### Note output format

Writer produces Obsidian markdown with YAML frontmatter (`type`, `created`, `tags`, `sources`) and sections: `## Core Concept`, `## Subtopics`, `## Connections` (placeholder filled by Linker), `## Sources`. Linker indexes vault by **filename stem** (not H1 heading) so wikilinks always resolve in Obsidian; it only injects into the `<!-- filled by Linker -->` placeholder and inline in the body.

## Testing conventions

- **Cache tests**: pass `db_path=":memory:"` + use the `reset_connections` autouse fixture (clears `cache._connections` before/after each test) for isolation.
- **Agent tests**: mock `anthropic.Anthropic` and `firecrawl.FirecrawlApp` at the module level (e.g. `patch("noter.agents.planner.anthropic.Anthropic")`). Use `pytest-mock`'s `mocker` fixture.
- **Writer/Linker tests**: use `tmp_path` for the vault filesystem.
- No test touches the real `~/.pesquisa/cache.db` or makes real network calls.
- Test files mirror `src/noter/` under `tests/`.

## Workflow rules

- **Run ruff** after every code write (command above).
