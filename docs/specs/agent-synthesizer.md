# Synthesizer Agent

Transforms raw content from multiple sources into structured knowledge, eliminating redundancy and organizing by subtopic according to the Planner's plan.

## Inputs

- `plan: PlannerOutput` — Planner output
- `sources: list[SourceResult]` — Searcher output (url, title, content)

## Output

```python
[
  {
    "note_title": str,
    "core_concept": str,
    "subtopics": [
      {
        "title": str,
        "content": str
      }
    ],
    "sources_used": [{"url": str, "title": str}]
  }
]
```

One entry per planned note (list of one item if `generate_multiple_notes: false`).

## Logic

- Receives all sources at once in the context
- The prompt instructs Claude to follow the `focus` of each note defined by the Planner
- Eliminates repeated information across sources
- Assigns each excerpt to the correct note when there are multiple notes
- Does not invent information — only synthesizes what is in the sources

## Context Considerations

- Truncate each source to ~3000 tokens before sending
- If total exceeds the limit: prioritize user sources and the most relevant by title

## Claude Tools

None — structured response via JSON mode.

## Tasks

- [ ] Write the Synthesizer prompt
- [ ] Implement source truncation by context limit
- [ ] Implement Claude call with structured output
- [ ] Validate that user sources are prioritized in context
- [ ] Unit tests (Claude mocked):
  - `test_user_sources_prioritized_in_context`
  - `test_truncation_respects_token_limit`
  - `test_multiple_notes_generated_for_broad_topic`
  - `test_one_note_output_for_simple_topic`
