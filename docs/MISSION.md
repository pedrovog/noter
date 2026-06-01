# noter — Mission Document

## What It Is

noter is a CLI tool that accepts a topic string, researches it autonomously on the web, and writes one or more permanent notes to an Obsidian vault's `00 - Inbox/` folder for human review. It is a personal knowledge assistant, not a publishing tool.

## Problem It Solves

Manually researching a topic, reading multiple sources, and writing a structured Obsidian note takes 30–60 minutes. noter reduces this to a single command by automating the full pipeline: search → scrape → synthesize → write → link.

## Success Criteria

- Running `noter "topic"` produces at least one coherent `.md` note in `00 - Inbox/` with correct frontmatter, body, and `[[wikilinks]]` to related vault notes.
- Re-running the same topic within the TTL window hits the cache instead of scraping again.
- All five pipeline agents complete without crashing for a simple topic.

## Hard Constraints (Non-Negotiable)

| Constraint | Rationale |
|---|---|
| CLI only — no web UI, no API server | Personal tool, single user |
| No authentication or multi-user support | Out of scope by design |
| SQLite only for persistence — no Redis, no Postgres | Keep deployment to zero infrastructure |
| No Docker or containerization | Local install only |
| Output only to Obsidian vault via filesystem | No syncing, no cloud storage |
| Python 3.12, typer for CLI | Locked stack per spec |
| LLM calls only via Anthropic SDK (Claude Sonnet 4.6) | No OpenAI, no local models |
| Firecrawl only for scraping | No Playwright, no Selenium |
| No streaming LLM responses | Batch pipeline, structured JSON output only |

## Explicit Out of Scope

- Web scraping beyond Firecrawl (no custom crawlers)
- Note editing or updating existing notes (write-once to Inbox)
- Semantic search or vector embeddings
- Scheduling or background daemon mode
- Plugin or extension system
- Any UI beyond terminal stdout

## Guiding Principles

1. **Fail gracefully, never silently**: a Firecrawl failure on one URL must log a warning and continue — not crash the pipeline.
2. **No invention**: the Synthesizer and Writer agents must only work with information from scraped sources. No hallucinated content.
3. **Cache-first**: always check `scrape_cache` before hitting any external API.
4. **One responsibility per agent**: agents do not call each other. The Orchestrator is the only component that sequences them.
5. **Tests use real contracts**: agent tests mock the Claude client and Firecrawl client, but use the real schemas. Cache tests use `:memory:` SQLite — never the filesystem cache.
