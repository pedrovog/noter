# noter — Technical Specification

## Pipeline Overview

```
CLI (cli.py)
  └─ orchestrator.run(topic, vault_path, user_urls, n_sources, cache_ttl, no_cache, no_search)
       ├─ planner.run(topic)                   → PlannerOutput
       ├─ searcher.run(plan, user_urls, ...)    → list[SourceResult]
       ├─ synthesizer.run(plan, sources)        → list[SynthesizedNote]
       ├─ writer.run(synth_notes, vault_path)   → list[str]  (file paths)
       └─ linker.run(note_paths, vault_path)    → int  (links injected count)
```

All agents live in `src/noter/agents/`. Each is a plain module with a `run()` function — no classes.

---

## Data Schemas

All schemas defined with Pydantic v2 in `src/noter/schemas.py`.

```python
# Planner output
class NoteSpec(BaseModel):
    title: str
    subtopics: list[str]
    focus: str

class PlannerOutput(BaseModel):
    main_title: str
    generate_multiple_notes: bool
    notes: list[NoteSpec]
    search_queries: list[str]

# Searcher output
class SourceResult(BaseModel):
    url: str
    title: str
    content: str          # scraped markdown
    source: Literal["auto", "user"]
    from_cache: bool

# Synthesizer output
class SubtopicContent(BaseModel):
    title: str
    content: str

class SourceRef(BaseModel):
    url: str
    title: str

class SynthesizedNote(BaseModel):
    note_title: str
    core_concept: str
    subtopics: list[SubtopicContent]
    sources_used: list[SourceRef]
```

---

## Component Contracts

### 1. CLI (`src/noter/cli.py`)

Entry point via typer. Validates inputs, loads env, calls `orchestrator.run()`.

**Arguments:**
```
noter <tema>
  --source URL            # repeatable, 0..N user URLs
  --source-file PATH      # .txt file, one URL per line
  --no-search             # skip automatic web search (Track A)
  --sources INT           # max automatic sources, default 5
  --cache-ttl INT         # cache TTL in days, default 30
  --no-cache              # bypass cache reads and writes
```

**Validation rules (fail fast before pipeline):**
- `--source-file` path must exist
- Each URL (from `--source` and file) must match `^https?://`
- `--sources` must be >= 1
- `VAULT_PATH` env var must point to an existing directory

---

### 2. Cache (`src/noter/cache.py`)

SQLite at `~/.pesquisa/cache.db`. Created automatically on first run.

**Schema:**
```sql
CREATE TABLE scrape_cache (
    url          TEXT PRIMARY KEY,
    content      TEXT NOT NULL,
    scraped_at   TEXT NOT NULL,  -- ISO 8601
    content_hash TEXT NOT NULL
);

CREATE TABLE url_usage (
    url        TEXT NOT NULL,
    note_path  TEXT NOT NULL,
    used_at    TEXT NOT NULL     -- ISO 8601
);
```

**Functions:**
```python
def get_cached(url: str, ttl_days: int, db_path: str = DEFAULT_DB) -> str | None
def save_cache(url: str, content: str, db_path: str = DEFAULT_DB) -> None
def register_usage(url: str, note_path: str, db_path: str = DEFAULT_DB) -> None
def check_duplicate(url: str, db_path: str = DEFAULT_DB) -> list[str]  # returns note_paths
```

**Rules:**
- `get_cached` returns `None` if expired or missing.
- `save_cache` computes `content_hash` with `hashlib.sha256`.
- `check_duplicate` returns all `note_path` values for the URL; empty list = no duplicate.
- All tests pass `db_path=":memory:"`.

---

### 3. Planner (`src/noter/agents/planner.py`)

Single Claude call, JSON mode. No tools.

```python
def run(topic: str) -> PlannerOutput
```

**Decision logic:**
- Simple topic (e.g. "what is backpropagation") → `generate_multiple_notes: False`, one note.
- Broad topic (e.g. "RAG") → `generate_multiple_notes: True`, one note per major subtopic.
- Threshold: more than 3 natural and distinct subtopics → multiple notes.
- `search_queries` must differ from the topic to maximize search coverage.

**Error handling:**
- Invalid JSON response → retry once → raise `PlannerError`.

---

### 4. Searcher (`src/noter/agents/searcher.py`)

No Claude calls. Calls Firecrawl and public APIs.

```python
def run(
    queries: list[str],
    user_urls: list[str],
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
    no_search: bool,
) -> list[SourceResult]
```

**Track A — Automatic search (skipped if `--no-search`):**
1. Firecrawl `/search` for each query in `search_queries`.
2. arXiv API search — abstracts + links.
3. Wikipedia API — main article if exists.
4. Respects `n_sources` across all three sub-sources combined.
5. Checks `scrape_cache` before scraping each URL.

**Track B — User URLs (always runs):**
1. Checks `scrape_cache` first.
2. Scrapes via Firecrawl `/scrape` if not cached.
3. No limit — all user URLs are always processed.
4. Prints `⚠ <url> already used in [[note_title]]` if `check_duplicate` returns hits.

**Parallelism:** Tracks A and B run concurrently via `asyncio` or `ThreadPoolExecutor`. Within Track A, multiple queries run in parallel.

**Error handling:** Firecrawl failure on a single URL → log warning, skip that URL, continue.

**Post-run:** Save all new (non-cached) results to `scrape_cache`.

---

### 5. Synthesizer (`src/noter/agents/synthesizer.py`)

Single Claude call, JSON mode. No tools.

```python
def run(plan: PlannerOutput, sources: list[SourceResult]) -> list[SynthesizedNote]
```

**Context management:**
- Truncate each source to ~3000 tokens before sending.
- If total still exceeds limit: prioritize user sources (`source == "user"`) then rank by title relevance.


**Rules:**
- Only synthesizes information present in sources — no invention.
- Follows the `focus` field from each `NoteSpec` when distributing content.
- One `SynthesizedNote` per planned note.

---

### 6. Writer (`src/noter/agents/writer.py`)

Claude call for tag inference. File I/O for the rest.

```python
def run(synth_notes: list[SynthesizedNote], vault_path: str) -> list[str]
```

**Output format:**
```markdown
---
type: permanent
created: YYYY-MM-DD
tags: [tag1, tag2, tag3]
sources:
  - url: https://...
    title: "Source Title"
---

# Note Title

## Core Concept

<introductory paragraph>

## Subtopics

### Subtopic 1

<content>

## Connections

<!-- filled by Linker -->

## Sources

- [Title](url)
```

**Rules:**
- File name = sanitized note title (strip special chars, replace spaces with spaces — keep readable).
- Do not overwrite existing files: append ` (2)`, ` (3)`, etc.
- Tags: 3–5 lowercase tags inferred by Claude from title + concept.
- `## Connections` left empty — Linker fills it.
- Returns list of absolute file paths created.

---

### 7. Linker (`src/noter/agents/linker.py`)

Single Claude call, JSON mode. File I/O for index + patch.

```python
def run(note_paths: list[str], vault_path: str) -> None
```

**Steps:**
1. **Index:** Recursively read all `.md` in `vault_path`. Extract title from `# Heading` or filename. Build `dict[title, path]`.
2. **Detect:** Send note content + vault title list to Claude. Claude returns substitutions: `{original: str, with_link: str}`.
3. **Inject:** Apply substitutions. Add linked titles to `## Connections`.

**Rules:**
- No self-reference (don't link a note to itself).
- First occurrence only — no duplicate links in body.
- Never modify frontmatter.
- If no links found: leave `## Connections` empty, exit cleanly.

---

### 8. Orchestrator (`src/noter/orchestrator.py`)

Sequences all agents. Manages progress output. Registers URL usage.

```python
def run(
    tema: str,
    user_urls: list[str],
    n_sources: int,
    cache_ttl: int,
    no_cache: bool,
    no_search: bool,
) -> None
```

**Progress stdout format:**
```
[Planner]      2 notes planned — ['RAG basics', 'Knowledge graphs']
[Searcher]     7 sources (2 from cache)
               ⚠ https://arxiv.org/... already used in [[GraphRAG]]
[Synthesizer]  Synthesizing...
[Writer]       RAG.md | Knowledge Graphs.md
[Linker]       4 links injected

Done. 2 note(s) in 00 - Inbox/ awaiting review.
```

**Error handling:**
- Firecrawl URL failure → logged, skipped (Searcher handles this).
- Claude JSON parse error → one retry → log + skip that agent's output.
- No sources collected → warn user, continue to Synthesizer with empty list.
- Linker failure → log warning, do not delete already-written notes.

**Post-pipeline:** Call `cache.register_usage(url, note_path)` for every `(source, note)` pair.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `FIRECRAWL_API_KEY` | Yes | Firecrawl API key |
| `VAULT_PATH` | Yes | Absolute path to Obsidian vault root |

---

## Project Layout

```
src/noter/
├── cli.py
├── orchestrator.py
├── cache.py
├── schemas.py
└── agents/
    ├── planner.py
    ├── searcher.py
    ├── synthesizer.py
    ├── writer.py
    └── linker.py

tests/
├── test_cache.py
├── test_orchestrator.py
└── agents/
    ├── test_planner.py
    ├── test_searcher.py
    ├── test_synthesizer.py
    ├── test_writer.py
    └── test_linker.py
```

---

## Testing Rules

- Cache tests: always pass `db_path=":memory:"`.
- Agent tests: mock `noter.llm.chat` (returns the raw response string) and `firecrawl.FirecrawlApp`.
- Writer tests: use `tmp_path` (pytest fixture) for vault filesystem.
- Linker tests: use `tmp_path` for vault.
- No test should make real network calls or touch `~/.pesquisa/cache.db`.
