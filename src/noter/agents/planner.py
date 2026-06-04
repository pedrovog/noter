import json
import logging
import os

import anthropic

from noter.config import PLANNER_MODEL
from noter.exceptions import PlannerError
from noter.schemas import PlannerOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a research planning assistant. Analyze the given topic and decide how to \
structure one or more Obsidian notes about it.

Decision rules:
- Simple / atomic topic (e.g. "what is backpropagation") → one note, \
generate_multiple_notes: false.
- Broad area with more than 3 natural and distinct subtopics (e.g. "RAG", \
"distributed systems") → one note per major subtopic, generate_multiple_notes: true.

Respond with a single valid JSON object — no markdown, no explanation, just JSON.

Schema:
{
  "main_title": "<overall research title>",
  "generate_multiple_notes": <true|false>,
  "notes": [
    {
      "title": "<note title>",
      "subtopics": ["<subtopic>", ...],
      "focus": "<specific synthesis instruction for this note>"
    }
  ],
  "search_queries": ["<query>", ...]
}

Rules for search_queries:
- Provide 3–5 queries.
- Queries must differ from the original topic to maximise search coverage.
- Use specific technical terms, not the exact topic string.
"""


def run(topic: str) -> PlannerOutput:
    """Return a structured research plan for the given topic.

    Raises:
        PlannerError: if Claude returns invalid JSON after one retry.
    """
    logger.debug("Planner: requesting plan for topic=%r model=%s", topic, PLANNER_MODEL)
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    for attempt in range(2):
        message = client.messages.create(
            model=PLANNER_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Plan the research notes for: {topic}"}],
        )
        block = message.content[0]
        if not isinstance(block, anthropic.types.TextBlock):
            raise PlannerError(f"Unexpected content block type: {type(block).__name__}")
        raw = block.text.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
        try:
            result = PlannerOutput.model_validate(json.loads(raw))
            logger.debug(
                "Planner: parsed %d note(s), %d search queries",
                len(result.notes),
                len(result.search_queries),
            )
            return result
        except Exception as exc:
            if attempt == 1:
                raise PlannerError(
                    f"Planner returned invalid output after 2 attempts: {exc}"
                ) from exc
            logger.debug("Planner: attempt %d failed to parse, retrying: %s", attempt + 1, exc)

    raise PlannerError("Planner failed")  # unreachable; satisfies type checker
