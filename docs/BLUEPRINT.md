# Project Blueprint: noter

## Value Proposition

noter is a CLI tool for researchers and knowledge workers who use Obsidian. It automates the full research pipeline — web search, scraping, synthesis, and note formatting — so that running a single command produces a permanent, well-linked Obsidian note in under a minute. Unlike generic AI chat tools, noter writes directly to your vault with correct frontmatter and wikilinks already injected.

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Type hints, asyncio, broad library support |
| CLI | typer | Declarative, autocompletion, clean UX |
| LLM | Claude Sonnet 4.6 via Anthropic SDK | Structured JSON output, large context |
| Scraping | Firecrawl | Handles JS-rendered pages, clean markdown output |
| Persistence | SQLite (`cache.db`) | Zero infrastructure, embedded |
| Schemas | Pydantic v2 | Strict validation, IDE support |
| Tests | pytest | Standard, integrates with `tmp_path` and monkeypatch |

## MVP Scope

### In Scope

- **CLI entrypoint**: `noter <tema>` with all flags (`--source`, `--source-file`, `--no-search`, `--sources`, `--cache-ttl`, `--no-cache`).
- **Planner agent**: Claude decides single vs. multiple notes and generates search queries.
- **Searcher agent**: Firecrawl + arXiv + Wikipedia in parallel, with cache-first logic and user URL scraping.
- **Synthesizer agent**: Claude deduplicates and structures scraped content per note plan.
- **Writer agent**: Produces valid Obsidian `.md` files with YAML frontmatter and inferred tags.
- **Linker agent**: Injects `[[wikilinks]]` from existing vault titles into new notes.
- **SQLite cache**: TTL-based scrape cache + URL usage tracking with duplicate warnings.

### Out of Scope

- Web UI or REST API
- Multi-user or authentication
- Note editing (notes are write-once to Inbox)
- Semantic search or vector embeddings
- Docker or any cloud deployment
- Streaming LLM responses
- Scheduled or daemon mode

## Implementation Phases

### Phase 1: Project Skeleton + Cache
**Goal:** Installable package with a working cache layer and a stub CLI.
**Deliverables:**
- `pyproject.toml` with all dependencies declared
- `.env.example` with the three required variables
- `src/noter/` layout: `cli.py`, `orchestrator.py`, `cache.py`, `schemas.py`, `agents/` (empty stubs)
- `cache.py` fully implemented with all four functions
- Unit tests for cache passing with `:memory:`
- `noter --help` runs without error
**Estimate:** 1 session

---

### Phase 2: Planner + Schemas
**Goal:** First real Claude call producing a validated, structured plan.
**Deliverables:**
- All Pydantic schemas in `schemas.py`
- `planner.py` with working Claude call and JSON output
- Prompt written and tested against mocked Claude responses
- Unit tests: simple topic → one note, broad topic → multiple notes, invalid JSON → exception
**Estimate:** 1 session

---

### Phase 3: Searcher
**Goal:** Content collection working end-to-end with cache.
**Deliverables:**
- `searcher.py` with Track A (Firecrawl + arXiv + Wikipedia) and Track B (user URLs)
- Parallel execution between tracks
- Cache hit/miss logic wired to `cache.py`
- Duplicate URL warning output
- Unit tests: all 6 cases from spec
**Estimate:** 1–2 sessions

---

### Phase 4: Synthesizer + Writer + Linker
**Goal:** Full pipeline producing real Obsidian notes.
**Deliverables:**
- `synthesizer.py` with context truncation and user-source prioritization
- `writer.py` with frontmatter generation, tag inference, file sanitization, no-overwrite logic
- `linker.py` with vault indexer, Claude-based link detection, in-place file patching
- Unit tests for all three agents
**Estimate:** 2 sessions

---

### Phase 5: Orchestrator + Integration
**Goal:** All agents connected; full pipeline runs from CLI.
**Deliverables:**
- `orchestrator.run()` sequencing all agents with progress stdout
- Error handling per agent (log + continue, not crash)
- URL usage registration after pipeline completes
- Integration tests: 3 topics (simple, medium, broad) against real APIs
- Validation: frontmatter correctness, link injection, cache hit on re-run, duplicate URL warning
**Estimate:** 1–2 sessions

## How to Use This Blueprint for SDD

Each session with Claude should:
1. Reference `MISSION.md` to stay in scope.
2. Reference the relevant section of `TECHNICAL_SPEC.md` for the component being built.
3. Work on one phase at a time — do not start Phase N+1 until Phase N tests pass.
4. Keep agent modules under ~150 lines; split if larger.
