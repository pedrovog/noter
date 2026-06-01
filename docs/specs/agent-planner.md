# Planner Agent

First Claude call in the pipeline. Receives the topic and decides the work structure before any search occurs.

## Inputs

- `topic: str` — string provided by the user via CLI

## Output

```python
{
  "main_title": str,
  "generate_multiple_notes": bool,
  "notes": [
    {
      "title": str,
      "subtopics": [str],
      "focus": str  # focus instruction for the Synthesizer
    }
  ],
  "search_queries": [str]  # search terms optimized for the Searcher
}
```

## Decision Logic

- Simple topic (e.g. "what is backpropagation") → `generate_multiple_notes: false`, one note
- Broad topic (e.g. "RAG") → `generate_multiple_notes: true`, one note per major subtopic
- Threshold: more than 3 natural and distinct subtopics → multiple notes

## Prompt

The prompt instructs Claude to:
1. Identify whether the topic is an atomic concept or a broad area
2. List natural subtopics
3. Decide note granularity
4. Generate optimized search queries (different from the original topic for broader coverage)

## Claude Tools

None — structured response via JSON mode.

## Tasks

- [ ] Write the Planner prompt
- [ ] Define output schema (Pydantic or TypedDict)
- [ ] Implement Claude call with structured output
- [ ] Unit tests (Claude mocked):
  - `test_simple_topic_generates_one_note`
  - `test_broad_topic_generates_multiple_notes`
  - `test_search_queries_generated`
  - `test_invalid_output_raises_exception`
