# Orchestrator

Connects all agents in sequence, manages state between them, displays progress in the terminal, and registers URL usage in the cache at the end.

## Flow

```python
def run(topic, user_urls, n_sources, cache_ttl, no_cache, no_search):

    # 1. Planner
    plan = planner.run(topic)
    print(f"[Planner]     {len(plan.notes)} note(s) — {plan.search_queries}")

    # 2. Searcher
    sources = searcher.run(
        queries=plan.search_queries,
        user_urls=user_urls,
        n_sources=n_sources,
        cache_ttl=cache_ttl,
        no_cache=no_cache,
        no_search=no_search,
    )
    print(f"[Searcher]    {len(sources)} sources ({sum(s.from_cache for s in sources)} from cache)")

    # 3. Synthesizer
    synth_notes = synthesizer.run(plan, sources)

    # 4. Writer
    paths = writer.run(synth_notes)
    print(f"[Writer]      {[Path(p).name for p in paths]}")

    # 5. Linker
    linker.run(paths)
    print("[Linker]      Links injected.")

    # 6. Register usage in cache
    for source in sources:
        for path in paths:
            cache.register_usage(source.url, path)

    print(f"\nDone. {len(paths)} note(s) in 00 - Inbox/ awaiting review.")
```

## Expected Terminal Output

```
$ noter "RAG with knowledge graphs"

[Planner]       2 notes planned: "RAG", "Knowledge Graphs"
[Searcher]      7 sources (5 automatic, 2 from user) — 2 from cache
                ⚠ https://arxiv.org/abs/2310.11511 already used in [[GraphRAG]]
[Synthesizer]   Synthesizing...
[Writer]        RAG.md created | Knowledge Graphs.md created
[Linker]        4 links injected

Done. 2 note(s) in 00 - Inbox/ awaiting review.
```

## Error Handling

- Firecrawl fails on one URL → log warning, continue with the rest
- Claude returns invalid JSON → retry once, then log and skip the agent
- Not enough sources → proceed with what was collected, warn the user

## Tasks

- [ ] Build agent call sequence
- [ ] Implement terminal progress output
- [ ] Per-agent error handling
- [ ] Register URL usage in cache after writing
- [ ] Unit tests (all agents mocked):
  - `test_full_flow_correct_sequence`
  - `test_urls_registered_in_cache_after_writing`
  - `test_searcher_failure_propagates_error`
  - `test_linker_failure_does_not_delete_notes`
