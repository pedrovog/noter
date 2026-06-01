# noter — Overview

CLI that, given a topic, researches sources on the web, synthesizes the content, and generates a permanent note in the Obsidian vault at `00 - Inbox/` awaiting review.

## Architecture

```
input: string (topic) + optional URLs
         ↓
[Planner]      — breaks the topic into subtopics, decides depth
         ↓
[Searcher]     — two parallel tracks:
                   a) automatic search (Firecrawl, arXiv, Wikipedia)
                   b) scraping of user-supplied URLs
                 → merged results
         ↓
[Synthesizer]  — reads results, removes redundancy, extracts key concepts
         ↓
[Writer]       — generates note in Obsidian format with correct frontmatter
         ↓
[Linker]       — reads the vault and injects [[links]] to related notes
         ↓
output: note in 00 - Inbox/ awaiting review
```

## Stack

| Component    | Choice                          |
|--------------|---------------------------------|
| LLM          | Claude Sonnet 4.6 via API       |
| Scraping     | Firecrawl                       |
| Language     | Python 3.12                     |
| Persistence  | `.md` files + SQLite            |
| CLI          | typer                           |

## Tasks

### 1. Project setup
- [ ] Create Python folder structure
- [ ] Configure `pyproject.toml`
- [ ] Create `.env.example`
- [ ] Layout `src/noter/agents/`, `cache.py`, `cli.py`, `orchestrator.py`
- [ ] Mirror `tests/` from `src/` structure

### 2. CLI
- [ ] Entry point with `typer`
- [ ] Positional argument `topic`
- [ ] `--source` (multiple), `--source-file` (.txt file)
- [ ] `--no-search`, `--sources` (int, default 5)
- [ ] `--cache-ttl` (int, default 30), `--no-cache`
- [ ] Validation: file exists, valid URLs

### 3. SQLite Cache
- [ ] Database at `~/.pesquisa/cache.db`
- [ ] Table `scrape_cache (url PK, content, scraped_at, content_hash)`
- [ ] Table `url_usage (url, note_path, used_at)`
- [ ] Functions: `get_cached`, `save_cache`, `register_usage`, `check_duplicate`
- [ ] Unit tests with in-memory database

### 4. Agents
- [ ] [Planner](agent-planner.md)
- [ ] [Searcher](agent-searcher.md)
- [ ] [Synthesizer](agent-synthesizer.md)
- [ ] [Writer](agent-writer.md)
- [ ] [Linker](agent-linker.md)
- [ ] [Orchestrator](orchestrator.md)

### 5. Integration tests
- [ ] Choose 3 vault topics (simple, medium, broad)
- [ ] Validate generated frontmatter
- [ ] Validate injected links
- [ ] Validate cache hit on second run
- [ ] Validate duplicate URL warning

### 6. README
- [ ] Prerequisites and installation
- [ ] Environment variable configuration
- [ ] Full CLI argument reference with examples
- [ ] Cache behavior description
